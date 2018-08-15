from common_modules.common import *
from troposphere import Parameter

stackconfig = StackConfig()
mystack = Stack(stackconfig)


s3CF_parameters = {
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
    ),
    "product": Parameter(
        "Product",
        Type="String",
        Default="PT",
        Description="The product that is being deployed"
    ),
    "s3name": Parameter(
        "S3Name",
        Type="String",
        Description="Full DNS name of s3 bucket.",
    ),
    "path": Parameter(
        "Path",
        Type="String",
        Description="The subdirectory from within S3 bucket.",
    ),
    "acmarn": Parameter(
        "ACMarn",
        Type="String",
        Default="arn:aws:acm:us-east-1:123456:certificate/cert",
        Description="This is ARN of cert should work for all ",
    ),
    "rootobject": Parameter(
        "rootObject",
        Type="String",
        Default="index.html",
        Description="What should be served for /",
    ),
    "urls": Parameter(
        "URLs",
        Type="CommaDelimitedList",
        Description="Aliases supported by Distribution. url1, url2, url3",
    ),
}
for p in s3CF_parameters.values():
    mystack.template.add_parameter(p)


mystack.cloudfront_adder()
