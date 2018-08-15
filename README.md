Jinni
===

This utility generates CloudFormation stacks in AWS. It also has the ability to upload generated stacks, modify them and output information about them. It's fundamentally based on [this library](https://github.com/cloudtools/troposphere) and has been inspired by some of the work done [here](https://github.com/cloudtools/stacker_blueprints)

In some ways it's similar to [Terraform](https://www.terraform.io/) and it has it's own pros/cons which will be placed in a separate doc file later. 



### Install
` python setup.py install`


### Use

For the deploy and upload functions you need to have AWS credentials configured on your system. Since this relies on the boto library it will expect to find credentials in one of the following places:

* ~/.aws/credentials
* ~/.aws/config
* Environment Variables
* /etc/boto.cfg
* ~/.boto

More information about boto credentials can be found [here](http://boto3.readthedocs.io/en/latest/guide/configuration.html)

* `jinni delete` - Takes a stack name as a parameter and deletes it. 
* `jinni deploy` - takes two parameters: stack name and an ami id. Currently only works with the regulator stack (deprecated functionality, jinni update should be used instead)
* `jinni info` - Take a stack name as a parameter (from jinni list). Will show a summary of stack resources including instances, ips, DNS records, ELBs, etc. 
* `jinni list` - shows existing CF stacks in AWS for your account
* `jinni modules` - shows available modules from which stacks can be created
* `jinni show` - Takes a module name as a parameter and outputs CF json template, which could be manually uploaded to AWS
* `jinni update` - This can update either stack parameters or the entire template. It takes a '--parameter' option which is a list of parameters in a format of `key=value, key2=value2" and/or a '--generator' option which will update the template for the stack from a given generator
* `jinni upload` - Takes a module name as a parameter. It will prompt for any required parameters specified by the module and will attempt to create the CF stack in AWS.
* `jinni validate` - Takes a module name as a parameter. Will validate the template against Cloudformation AWS API. More accurate test than simply for valid JSON.

### Modules

Key components for creating different stacks live in the [stack modules](https://github.com/mediaplatform/jinni/tree/master/stack_modules) package. Currently available modules are:

* **redis** - creates an elasticache Redis cluster
* **kinesis** - creates a Kinesis setup in aws
* **s3Cloudfront_generator**  - creates a Cloudfront distribution
* **vpc_generator** - creates an opininated VPC setup
* **elasticsearch_generator** - creates an ES cluster in AWS

Fundamentally, these are somewhat arbitrary. The current plan is to evolve this tool where you will select a particular "blueprint" which will setup a version of the stack in AWS. Primary logic exists in the common library and any of the components can be arbitrarily mixed and matched. See [example_generator.py]((https://github.com/mediaplatform/jinni/tree/master/stack_modules/example_generator.py) for a more detailed explanation of what's possible. 


### Docs

More information about specific modules and how they work can be located in the [docs directory](https://github.com/mediaplatform/jinni/tree/master/docs)

### Libraries

The common libraries can be found in the [common modules](https://github.com/mediaplatform/jinni/tree/master/stack_modules/common_modules) package. 
Generally speaking, most functionality for the tools lives in that package. The generators are simple wrappers that provide logic and parameters for specific stacks.

### Config

Configuration files are located in the [config](https://github.com/mediaplatform/jinni/tree/master/stack_modules/config) directory. In most cases, if you're making modifications you only need to adjust the configuration file.
There is a global config file `global.yml` which supplies the following parameters:

* keyname - *default key that instances will be launched with*
* vpcid - *default VPC ID*
* iam_role - *default IAM Role for the instances*
* subnets - *default private subnets in our VPC*
* public_subnets - *default public subnets in our VPC*

For the most part, this configuration should not be changed. Each parameter can be overriden in the stack specific configuration file. 
Each stack or stack module provides its own configuration file. If you need to override default settings for a particular stack you need to create an `/etc/stack_generator` directory and place the configuration files in there. 

Most configuration files will have the following parameters:

* apps - *this is a list of applications that make up the stack. The keys in that list are typically application names*
* size - *controls the size of the instances that will be launched*
* ami_id - *controls the starting AMI for the instances*
* count - *how many instances to launch*
* role - *this parameter controls the tags that will be assigned to the instances*
* extra_roles - *optional parameter. If set, it will assign additional tags to the instances*
* elb - True/False. *Controls if the application will get an ELB or not*
* type - *optional parameter. Controls if the ELB will be internal or public facing*
* alb - True/False. *Will create an Application Load Balancer, rather than an ELB*
* dns - *optional parameter. If set, will create a CNAME entry mapping to the ELB*
* ports - *optional parameter. If set will maps the ELBs to these ports, rather than 80*
* elb_check_type - *optional parameter. Can be set to HTTP or TCP*
* elb_check_path - *optional parameter. Defaults to "/", but can be a specific health page on an application


### Contributors

* [afreyman](https://github.com/afreyman)
* [sjhafran](https://github.com/sjhafran)
* [mproctor13](https://github.com/mproctor13)
* [johnsiciliano](https://github.com/johnsiciliano)

````
The MIT License

Copyright <2018> <MediaPlatform>

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

