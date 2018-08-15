from common_modules.common import *
from common_modules.parameters import *

stackconfig = StackConfig()
# stackconfig.loadlocalconfig("vbi_kinesis.yml")
mystack = Stack(stackconfig)
mystack.description('Template for VBI Kinesis Stack')

kinesis_params = {
    "env": Parameter(
        "DeploymentEnvironment",
        Type="String",
        Default="DEV",
        Description="Environment you are building",
    ),
    "shardCount": Parameter(
        "KinesisShardCount",
        Type="String",
        Default="1",
        Description="Number of Shards for this Environment.",
    )
}

for p in (kinesis_params.values()):
    mystack.template.add_parameter(p)


mystack.kinesis_adder("queue", Ref("KinesisShardCount"))
