from common_modules.common import *
from common_modules.parameters import common_tags_as, common_tags
from common_modules.parameters import basic_parameters, asg_parameters, elb_parameters
from common_modules.vpc import *


private_subnets = []
public_subnets = []
stackconfig = StackConfig()
stackconfig.loadlocalconfig("vpc.yml")
mystack = Stack(stackconfig)
mystack.description('VPC Stack')

cidr = mystack.config['apps'].values()[0].get("cidr")

for p in (basic_parameters.values(), asg_parameters.values(), elb_parameters.values()):
    mystack.template.add_parameter(p)

# you must specify the CIDR mask in the config. Makes no sense to have it as a parameter since changing it would require
# essentially a new VPC

myvpc = Vpc(mystack.template, common_tags, cidr)


# overriding some global values here. Those were created with the assumption of an existing vpc
mystack.config['vpcid'] = Ref(myvpc.vpc)

# grab the pub and priv subnets from the template.
for i in myvpc.template.resources.iteritems():
    if 'PrivSub' in i[0]:
        private_subnets.append(Ref(i[0]))
    if 'PubSub' in i[0]:
        public_subnets.append(Ref(i[0]))

# same as for the VPC. Gotta override because these were assumed to be static in an existing vpc.
mystack.config['public_subnets'] = public_subnets
mystack.config['subnets'] = private_subnets
mystack.config['vpcid'] = Ref(myvpc.vpc)
mystack.sec_groups = []

# more overrides for listener protocol. By default we only support HTTP/HTTPS.
k8sELB = mystack.elb_adder("k8", None, Ref("Hostname"))
for l in k8sELB.Listeners:
    l.Protocol = "TCP"
    l.PolicyNames = Ref("AWS::NoValue")


# Create sec groups here.

rule_http_access = mystack.rule_adder(80)
rule_ssl_access = mystack.rule_adder(443)
rule_ssh_access_vpc = mystack.rule_adder(22, cidr=cidr)
rule_all_office_access = mystack.rule_adder(0, 65535)
k8group = mystack.group_adder('k8group', [rule_http_access, rule_ssl_access, rule_ssh_access_vpc, rule_all_office_access])



# adding some custom parameters. Again, some funky stuff below because we generally assume 1 AS group per stack.
# For the masters, in the AS group, the numbers shouldn't change.
# Add AS stack for masters

k8master_as_size = mystack.template.add_parameter(Parameter(
    "K8MasterCapacity",
    Default="3",
    Description="Must always be 3",
    Type="String",
    AllowedValues=["3"]
))

# need this extra tag for clusterID for k8s.
k8s_cluster_name = 'kubernetes.io/cluster/' + str(Ref("AWS::StackName"))
common_tags_as += AsTags(**{
    k8s_cluster_name: 'owned',
})


k8master_group = mystack.autoscaling_adder(common_tags_as, "K8MasterCapacity", "K8MasterCapacity",
                          "K8MasterCapacity", Ref("AMIID"), "t2.medium",
                          "k8group", loadbalancer=[Ref(k8sELB)],
                          keyname=Ref("SSHKeyName"))


k8worker_group = mystack.autoscaling_adder(common_tags_as, "InitCapacity", "MaxCapacity",
                          "MinInService", Ref("AMIID"), Ref("InstanceType"),
                          "k8group", keyname=Ref("SSHKeyName"))

# not ideal here, but again a similar issue with us assuming a single AS group for stack. Need to override tag values
#print k8master_group.as_group.Tags.tags
for i in k8worker_group.as_group.Tags.tags:
    for k, v in i.items():
        try:
            if 'k8_master' in v:
                i[k] = 'k8_worker'
        except TypeError:
            pass


#print mystack.template.to_json()
