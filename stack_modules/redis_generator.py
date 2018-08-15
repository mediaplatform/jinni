from troposphere import Ref, Tags

from common_modules.common import Stack, StackConfig
from common_modules.parameters import redis_parameters

redisconfig = StackConfig()
mystack = Stack(redisconfig)


for p in redis_parameters.values():
    mystack.template.add_parameter(p)

common_tags = Tags(
    env=Ref("DeploymentEnvironment"),
    Product=Ref("Product"),
    Name=Ref("Product"),
    Role=Ref("Product"),
    prometheus_node="yes"
)

mystack.redis_adder(Ref("RedisName"), common_tags)
