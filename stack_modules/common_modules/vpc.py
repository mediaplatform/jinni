import ipaddress
import random
import unicodedata
from troposphere import GetAtt
from troposphere import Ref, GetAZs, Select
from troposphere.iam import Role, Policy
from awacs.aws import Allow, Statement, Principal, Action, PolicyDocument
from awacs.sts import AssumeRole
from awacs import cloudformation
from troposphere.ec2 import Route, \
    VPCGatewayAttachment, SubnetRouteTableAssociation, Subnet, RouteTable, \
    VPC, EIP, InternetGateway, NatGateway


# defining VPC as a big class for initializing an opinionated stack. Only parameter that is passed is the CIDR mask and
# tags

class Vpc:

    def __init__(self, template, common_tags, vpc_cidr):
        self.template = template
        self.vpc_cidr = vpc_cidr
        self.public_subnet_list = []
        self.private_subnet_list = []
        self.nat_gateway = ""
        self.igw = ""
        self.k8_master_role = ""
        self.k8_worker_role = ""
        self.tags = common_tags
        self.azs = GetAZs("")

        self.vpc = self.__vpc_adder(vpc_cidr)
        # add nat/igw gateways here for both pub/priv subnets
        self.__add_internet_gateway()
        self.__add_nat_gateway()
        # add routing tables for pub/priv
        self.__add_route_table('PrivateRouteTable')
        self.__add_route_table('PublicRouteTable')

        # split the CIDR into 6 subnets, 3 for pub, 3 for pub.
        self.subnet_splitter()
        self.subnet_adder(self.private_subnet_list, 'PrivSubnet', 'PrivateRouteTable')
        self.subnet_adder(self.public_subnet_list, 'PubSubnet', 'PublicRouteTable')
        self.vpc_role_adder()

    def __vpc_adder(self, cidr):
        """ Creates VPC resource """
        vpc = self.template.add_resource(
            VPC(
                'VPC',
                CidrBlock=cidr,
                Tags=self.tags
            )
        )
        return vpc
    # this function handles both the creation of IGW and Attachment.

    def __add_internet_gateway(self):
        self.igw = self.template.add_resource(
            InternetGateway(
                'InternetGateway',
                Tags=self.tags
            )
        )
        self.template.add_resource(
            VPCGatewayAttachment(
                'AttachGateway',
                VpcId=Ref(self.vpc),
                InternetGatewayId=Ref(self.igw)
            )
        )
    # this function handles both the creation of NAT EIP and gateway

    def __add_nat_gateway(self):

        nat_ip = self.template.add_resource(
                EIP(
                    'NatEIP',
                    Domain="vpc"
                )
            )

        self.nat_gateway = self.template.add_resource(
            NatGateway(
                'Nat',
                AllocationId=GetAtt(nat_ip, 'AllocationId'),
                SubnetId=Ref('PubSubnet0')
            )
        )
        self.nat_gateway.DependsOn = 'PubSubnet0'

    def __add_route_table(self, route_table_name):

        self.template.add_resource(
            RouteTable(
                route_table_name,
                VpcId=Ref(self.vpc)
            )
        )
        route = self.template.add_resource(
            Route(
                route_table_name + str(random.randint(1, 999)),
                RouteTableId=Ref(route_table_name),
                DestinationCidrBlock='0.0.0.0/0',
            )
        )
        # assumption of a naming convention and a pretty simple use case here.
        if "Priv" in route_table_name:
            gateway = self.nat_gateway
            route.NatGatewayId = Ref(gateway)
            route.DependsOn = 'Nat'
        else:
            gateway = self.igw
            route.GatewayId = Ref(gateway)
            route.DependsOn = 'AttachGateway'

    # split subnets into at least 6 and assign them to two lists.

    def subnet_splitter(self):
        myrange = ipaddress.ip_network(unicode(self.vpc_cidr, "utf-8"))
        for i in range(1, 10):
            if len(list(myrange.subnets(prefixlen_diff=i))) >= 6:
                self.public_subnet_list = list(myrange.subnets(prefixlen_diff=i))[0:3]
                self.private_subnet_list = list(myrange.subnets(prefixlen_diff=i))[3:6]
                return

        # this only happens if we couldn't find the right split
        print "Couldn't split the CIDR range into 6 subnets. Exiting"
        exit(1)

    # add subnets and route tables.
    def subnet_adder(self, subnet_list, name_ref, route_table_name):

        for index, cidr in enumerate(subnet_list):
            self.template.add_resource(
                Subnet(
                    name_ref + str(index),
                    CidrBlock=str(cidr),
                    VpcId=Ref(self.vpc),
                    # not a fan of the below line, but will do for now. This basically exists to ensure that subnets are
                    # distributed between availability zones. However, since we are always creating 3 pub/priv subnets
                    # this will fail if there are less than 3 AZs in a given region. Ideally the subnet count &
                    # distribution would happen dynamically based on how many zones are available.
                    AvailabilityZone=Select(index, self.azs)
                )
            )
            self.template.add_resource(
                SubnetRouteTableAssociation(
                    route_table_name + str(index),
                    SubnetId=Ref(name_ref + str(index)),
                    RouteTableId=Ref(route_table_name)
                )
            )

    # will tighten this up later

    def vpc_role_adder(self):
        self.k8_master_role = self.template.add_resource(
            Role(
                'k8master',
                AssumeRolePolicyDocument=PolicyDocument(
                    Statement=[
                        Statement(
                            Effect=Allow,
                            Action=[AssumeRole],
                            Principal=Principal("Service", ["ec2.amazonaws.com"])
                        )
                    ]
                ),
                Policies=[
                    Policy(
                        PolicyName='k8master',
                        PolicyDocument=PolicyDocument(
                            Statement=[
                                Statement(
                                    Effect=Allow,
                                    Action=[
                                        Action('s3', 'List*'),
                                        Action('s3', 'Get*'),
                                        Action('ecr', '*'),
                                        Action('elasticloadbalancing', '*'),
                                        cloudformation.SignalResource,
                                        Action('ec2', 'Describe*'),
                                    ],
                                    Resource=['*']
                                )
                            ]
                        )
                    )
                ]
            )
        )
        self.k8_worker_role = self.template.add_resource(
            Role(
                'k8worker',
                AssumeRolePolicyDocument=PolicyDocument(
                    Statement=[
                        Statement(
                            Effect=Allow,
                            Action=[AssumeRole],
                            Principal=Principal("Service", ["ec2.amazonaws.com"])
                        )
                    ]
                ),
                Policies=[
                    Policy(
                        PolicyName='worker',
                        PolicyDocument=PolicyDocument(
                            Statement=[
                                Statement(
                                    Effect=Allow,
                                    Action=[
                                        Action('s3', 'List*'),
                                        Action('s3', 'Get*'),
                                        Action('ecr', '*'),
                                        cloudformation.SignalResource,
                                        Action('ec2', 'Describe*'),
                                        Action('sns', '*')
                                    ],
                                    Resource=['*']
                                )
                            ]
                        )
                    )
                ]
            )
        )


