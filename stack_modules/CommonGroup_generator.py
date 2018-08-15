from common_modules.common import *
from troposphere import Parameter, Export

# common magic
# global variables
stackconfig = StackConfig()
mystack = Stack(stackconfig)
mystack.description('Template for Admin Security Group')

# bunch of rules for security groups. They are fairly open for now, but will be tightened up later.
rule_all_access = mystack.rule_adder(0, 65535)
rule_ssh_access_vpc = mystack.rule_adder(22)


# Security group definitions. This should be simplified to get rid of redundancy.
common_admin_group = mystack.group_adder('CommonAdmin', [
    rule_all_access,
    rule_ssh_access_vpc
])


mystack.template.add_output([
    Output(
        "CommonAdmin",
        Value=Ref('CommonAdmin'),
        Export=Export(Join("-", ["CommonAdminId", Ref('DeploymentEnvironment')]))
    )
])
