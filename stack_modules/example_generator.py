# A number of imports that are necessary for the generator. 
from common_modules.common import *
from common_modules.parameters import common_tags_as
from common_modules.parameters import basic_parameters, asg_parameters, elb_parameters

# Initialization of the Stack object. 
stackconfig = StackConfig()

# if the stack will have a specific configuration file it will be loaded here. 
stackconfig.loadlocalconfig("example.yml")
mystack = Stack(stackconfig)
mystack.description('Example stack')

# This adds the parameters that are necessary for this particular type of a stack. 
# These are essentially user prompts and also the values that can then be modified without updating 
# the template

for p in (basic_parameters.values(), asg_parameters.values(), elb_parameters.values()):
mystack.template.add_parameter(p)

# This will create any security group rules that are necessary for your stack
# Some examples are below. If only the port is supplied as a parameter, then it will be open to everyone
# alternatively, a cidr mask can be passed to restrict it further. 

rule_http_access = mystack.rule_adder(80)
rule_ssl_access = mystack.rule_adder(443)
rule_8080_access = mystack.rule_adder(8080)
rule_ssh_access = mystack.rule_adder(22, cidr='10.0.0.0/16')


# This creates a security group with the rules defined above
mystack.group_adder('example', [rule_http_access, rule_ssl_access,
rule_8080_access, rule_ssh_access])

# If you need to add an ELB as part of the stack it's done via an elb_adder function
MyExampleELB = mystack.elb_adder("example", None, Ref("Hostname"))

# If you need to add an autoscaling group as part of the stack, it's done via autoscaling_adder function
mystack.autoscaling_adder(common_tags_as, "InitCapacity", "MaxCapacity",
                          "MinInService", Ref("AMIID"), Ref("InstanceType"),
                          "example", loadbalancer=[Ref(MyExampleELB)], keyname=Ref("SSHKeyName"))



# If you need to add RDS to the stack it's done via rds_adder function. You would also need to import more parameters
# example below
from common_modules.parameters import rds_parameters
for p in (rds_parameters.values()):
mystack.template.add_parameter(p)
rule_rds_access = mystack.rule_adder(3306)
mystack.group_adder('VPCRDSSecurityGroup',
                    [
                        rule_rds_access
                    ],
                    description='VPCRDSSecurityGroup'
                    )
conditions = {
    "NotRestoringFromSnapshot": Equals(Ref("RDSSnapshot"), ""),
}

for w in conditions:
    mystack.template.add_condition(w, conditions[w])

mystack.rds_adder(Ref("RDSDBName"), Ref("RDSDBAllocatedStorage"), Ref("RDSDBSubnetGroup"),
[Ref("VPCRDSSecurityGroup")], Ref("RDSDBSize"))


# If you're adding a set of instances that are not part of the autoscaling group then that's done via 
# a process_config module. That might look something like this:

mystack.process_config(common_tags, 't2.medium')


# If you need to pass custom user data to the AS group you would reference your custom user data file
# in the autoscaling_adder function. An example might be below

mystack.autoscaling_adder(common_tags_as, "InitCapacity", "MaxCapacity",
                          "MinInService", Ref("AMIID"), Ref("InstanceType"),
                          "example", user_data_file="example_user_data.txt", loadbalancer=[Ref(MyExampleELB)], keyname=Ref("SSHKeyName"')