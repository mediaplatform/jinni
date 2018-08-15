from stack_modules.common_modules.common import *
from troposphere import Parameter, Tags

stackconfig = StackConfig()
mystack = Stack(stackconfig)

mystack.description('ElasticSearch Stack')

parameters = {
    "env": Parameter(
        "DeploymentEnvironment",
        Type="String",
        Default="DEV",
        Description="Environment you are building (DEV,QA,STG,PROD)",
    ),
    "ver": Parameter(
        "ProductVersion",
        Type="String",
        Default="6.1",
        Description="Version deploying (e.g. 6.1)",
    )
}

common_tags = Tags(
    env=Ref("DeploymentEnvironment"),
    Version=Ref("ProductVersion")
)

for p in parameters.values():
    mystack.template.add_parameter(p)
mystack.elasticsearch_cluster('elasticsearch')
