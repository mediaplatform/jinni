from troposphere import Parameter, Ref, Tags

from stack_modules.common_modules.common import *

# common magic
# global variables
stackconfig = StackConfig()
stackconfig.loadlocalconfig("config/solrzoomq.yml")
zookeepstack = Stack(stackconfig)
zookeepstack.description('Template for Solr, Zookeeper, AMQ Stack')
zookeepstack.template.add_mapping('RegionMap', {
    "us-east-1": {"AMIBASE": "ami-fce3c696", "AMITRANSCODER": "ami-39091e53"}
})

# what the user will be expected to input when launching the template.
parameters = {
    "base_url": Parameter(
        "BaseURL",
        Type="String",
        Default="mediaplatformdev.com",
        Description="This is the base URL for the environment"
    ),
    "env": Parameter(
        "DeploymentEnvironment",
        Type="String",
        Default="DEV",
        Description="Environment you are building (DEV,QA,STG,PROD)",
    ),

    "cert_name": Parameter(
        "CertName",
        Type="String",
        Default="arn:aws:iam::314826648217:server-certificate/mediaplatformQA_2017Mar05",
        Description="This has to be the right certificate for the environment",
        AllowedValues=[
            "arn:aws:iam::314826648217:server-certificate/star-mediaplatformdev-2017",
            "arn:aws:iam::314826648217:server-certificate/mediaplatformQA_2017Mar05"
        ],
        ConstraintDescription="must select a valid existing cert",
    )
}
common_tags = Tags(
    env=Ref("DeploymentEnvironment"),
)

for p in parameters.values():
    zookeepstack.template.add_parameter(p)
# bunch of rules for security groups. They are fairly open for now, but will be tightened up later.
rule_all_office_access = zookeepstack.rule_adder(0, 65535, '192.186.2.0/24')
rule_http_access = zookeepstack.rule_adder(80)
rule_ssl_access = zookeepstack.rule_adder(443)
rule_amq_admin_access = zookeepstack.rule_adder(8161)
rule_amq_access = zookeepstack.rule_adder(61616)
rule_solr_admin_access = zookeepstack.rule_adder(8983)
rule_zookeeper_access = zookeepstack.rule_adder(2181)
rule_ssh_access_vpc = zookeepstack.rule_adder(22, cidr='10.0.0.0/16')

# Security group definitions. This should be simplified to get rid of redundancy.
amq_group = zookeepstack.group_adder('amqgroup', [
    rule_http_access,
    rule_ssl_access,
    rule_all_office_access,
    rule_amq_access,
    rule_amq_admin_access,
    rule_ssh_access_vpc
])

solr_group = zookeepstack.group_adder('solrgroup', [
    rule_http_access,
    rule_all_office_access,
    rule_solr_admin_access,
    rule_ssh_access_vpc
])

zookeeper_group = zookeepstack.group_adder(
    'zookeepergroup',
    [
        rule_all_office_access,
        rule_zookeeper_access,
        rule_ssh_access_vpc,
    ]
)

# this needs to be done for self-referencing. Eventually all group definitions might become like that.
# For now Just zookeeper
zookeepstack.template.add_resource(
    ec2.SecurityGroupIngress(
        "AllAccessForZookeeper",
        IpProtocol='TCP',
        FromPort='0',
        ToPort='65535',
        SourceSecurityGroupId=Ref("zookeepergroup"),
        GroupId=Ref("zookeepergroup")
    )
)
# Function to add instances based on the definition.
for k, v in zookeepstack.config['apps'].iteritems():
    instance_list = []
    for index in xrange(v['count']):
        instance_list.append(
            zookeepstack.instance_adder(k, 't2.medium', v['ami_id'], 'zookeeperrole', '', index,
                                        common_tags))
zookeepstack.new_elb_adder('dorf')
waffles = zookeepstack.target_adder('smorf', 80, 'dorf', 'solr')
zookeepstack.target_rule_adder('corf', 'smorf', ['/api/*'], Ref(waffles))
# mystack.process_config(common_tags, 't2.medium')

zookeepstack.print_template()
