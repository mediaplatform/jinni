import click
import re
import pkgutil
import boto3
import botocore.session
import time
import imp
from botocore.exceptions import ClientError


# overriding the base ParamType to create a dict type
class BasedListSParamType(click.ParamType):
    name = 'dict'

    def convert(self, value, param, ctx):
        # if value is False:
        #     print "You need to pass some parameters with --parameters option"
        #     exit(1)
        if value:
            try:
                newvalue = dict([x.strip().split('=') for x in value.split(',')])
                return newvalue
            except Exception:
                print "Looks like you got a formatting error in your parameters. Check --help for syntax"
                exit(1)


class StackParametersConfigObject:
    def __init__(self, stack_name, input_params):
        if input_params is None:
            input_params = {}
        self.current_parameters = self.__get_stack_parameters(stack_name)
        self.current_parameters_keys = [item["ParameterKey"] for item in self.current_parameters]
        self.input_parameters = input_params
        self.input_parameters_keys = [x for x, y in self.input_parameters.iteritems()]
        self.generator_parameters = []
        self.generator_template = ""
        self.updated_parameters = []
        self.capabilities = []

    @staticmethod
    def __get_stack_parameters(stack_name):
        try:
            stack_definition = client.describe_stacks(StackName=stack_name)['Stacks']
            for s in stack_definition:
                stack_parameters = s['Parameters']
            return stack_parameters
        except Exception as e:
            print e
            exit(1)

    @staticmethod
    def __update_parameter_value(parameter, parameter_list, new=False):
        new_parameter = parameter.copy()
        if new:
            try:
                old_param = next(x for x in parameter_list if x["ParameterKey"] == new_parameter["ParameterKey"])
                parameter_list.remove(old_param)
            except StopIteration:
                pass
        else:
            new_parameter.pop('ParameterValue', None)
            new_parameter["UsePreviousValue"] = True

        parameter_list.append(new_parameter)

    def set_generator_parameters(self, generator):
        module = module_import(generator)
        for key in module.mystack.template.parameters.keys():
            self.generator_parameters.append(key)

    def set_generator_template(self, generator):
        module = module_import(generator)
        self.generator_template = module.mystack.template.to_json()

    def set_generator_capabilities(self, generator):
        module = module_import(generator)
        self.capabilities = module.mystack.capabilities

    def validate_input_parameters(self):
        new_generator_parameters = set(self.generator_parameters).difference(self.current_parameters_keys)
        new_input_parameters = set(self.input_parameters_keys).difference(self.current_parameters_keys)
        try:
            if new_generator_parameters and not new_generator_parameters.issubset(self.input_parameters_keys):
                print "Error. Looks like your template has new parameters which are " \
                      "not set with --parameters option. The parameters are:"
                for p in new_generator_parameters:
                    print p
                exit(1)

            if new_input_parameters and not new_input_parameters.issubset(self.generator_parameters):
                print 'Error. Looks like some parameters that you are passing do not exist on ' \
                      'this stack nor on the template. Check key spelling or available parameters. The parameters are:'
                for p in new_input_parameters.difference(self.generator_parameters):
                    print p
                exit(1)
        except Exception as e:
            print e
            exit(1)

    def update_stack_parameters(self):

        # update all parameters to use previous values
        for parameter in self.current_parameters:
            self.__update_parameter_value(parameter, self.updated_parameters)

        # If input parameters were passed, take the value and update existing parameters.
        for x, y in self.input_parameters.iteritems():
            input_parameter = {'ParameterKey': x, 'ParameterValue': y}
            self.__update_parameter_value(input_parameter, self.updated_parameters, new=True)


BASE_DICT = BasedListSParamType()

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
CF_STATUS_FILTERS = ['CREATE_COMPLETE', 'CREATE_IN_PROGRESS', 'ROLLBACK_IN_PROGRESS', 'ROLLBACK_FAILED',
                     'ROLLBACK_COMPLETE', 'DELETE_IN_PROGRESS', 'DELETE_FAILED', 'UPDATE_IN_PROGRESS',
                     'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_IN_PROGRESS',
                     'UPDATE_ROLLBACK_FAILED', 'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS',
                     'UPDATE_ROLLBACK_COMPLETE', 'REVIEW_IN_PROGRESS']
complete_status = ['CREATE_COMPLETE', 'UPDATE_COMPLETE']
failed_status = ['UPDATE_FAILED', 'CREATE_FAILED', 'ROLLBACK_IN_PROGRESS', 'UPDATE_ROLLBACK_IN_PROGRESS',
                 'UPDATE_ROLLBACK_COMPLETE']
failed_event = ['UPDATE_FAILED', 'CREATE_FAILED']

module_list = []
pkgpath = imp.find_module('stack_modules')[1]

session = botocore.session.get_session()
if session.get_config_variable('region') is None:
    client = boto3.client('cloudformation', region_name='us-east-1')
else:
    client = boto3.client('cloudformation')

for _, name, _ in pkgutil.iter_modules([pkgpath]):
    if 'generator' in name:
        i = re.sub('_generator$', '', name)
        module_list.append(i)


def get_stack_parameters(stack_name):

    try:
        stack_definition = client.describe_stacks(StackName=stack_name)['Stacks']
        for s in stack_definition:
            stack_parameters = s['Parameters']
        return stack_parameters
    except Exception as e:
        print e
        exit(1)


def update_stack(stack_name, stack):

    for p in stack.updated_parameters:
        if "ParameterValue" in p:
            click.echo("Updating " + p['ParameterKey'] + " to value " + p["ParameterValue"])

    try:
        # a little less then ideal here. Better to pass kwargs to function.
        if stack.generator_template:
            client.update_stack(StackName=stack_name, TemplateBody=stack.generator_template,
                                Parameters=stack.updated_parameters,
                                Capabilities=stack.capabilities)
        else:
            client.update_stack(StackName=stack_name, UsePreviousTemplate=True,
                                Parameters=stack.updated_parameters,
                                Capabilities=stack.capabilities)
    except ClientError as e:
        if 'No updates are to be performed' in e.response['Error']['Message']:
            print "Looks like you're trying to update the stack with the same parameter values that it's already " \
                  "using. That's not a valid operation"
            exit()
        else:
            print "Updating failed. Received error: %s" % e
            exit(1)
    status_progress(stack_name)


def module_import(module):
    module_name = 'stack_modules.' + module + '_generator'
    module = __import__(module_name, fromlist=[''])
    return module


def __dns_validator(param_name, parameters, param_value, default_value, description):
    dns_client = boto3.client('route53')
    parameter_url_names = ["DOMAIN".lower(), "BASEURL".lower()]
    try:
        for p in parameters:
            if any(s in p['ParameterKey'].lower() for s in parameter_url_names):
                dns_tld = p['ParameterValue']
                dns_full_name = param_value + "." + dns_tld

        if dns_tld is None:
                print "Base Domain URL could not be located. Exiting"
                exit(1)

        zone_id = dns_client.list_hosted_zones_by_name(DNSName=dns_tld)['HostedZones'][0]['Id']
        record_list = dns_client.list_resource_record_sets(HostedZoneId=zone_id, StartRecordName=dns_full_name)[
            'ResourceRecordSets'][0]

        if dns_full_name + "." == record_list['Name']:
            print "Hostname " + param_value + " already exists in " + dns_tld
            param_value = click.prompt(
                'Please put in the value for ' + param_name + ' (' + description + ')',
                default=default_value, type=str)
            __dns_validator(param_name, parameters, param_value, default_value, description)

    except Exception as e:
        print e


def stack_info(resourcetype, resourceid, stack_info_dict):

    if "Route53" in resourcetype:
        key = "DNS Resources:"
        stack_info_dict.setdefault(key, [])
        tld_domain = resourceid.partition('.')[2]
        try:
            dns_client = boto3.client('route53')
            zones = dns_client.list_hosted_zones()
            for z in zones['HostedZones']:
                if tld_domain + '.' == z['Name']:
                    zone_id = z['Id']
            resource_records = dns_client.list_resource_record_sets(HostedZoneId=zone_id, StartRecordName=resourceid)
            record_value = resource_records['ResourceRecordSets'][0]['ResourceRecords'][0]['Value']
            record_type = resource_records['ResourceRecordSets'][0]['Type']
            stack_info_dict[key].append(resourceid + "\t" + record_value + "\t" + record_type)
        except Exception as e:
            stack_info_dict[key].append("No resources could be found")
        return stack_info_dict
    elif "RDS" in resourcetype:
        key = "RDS Resources"
        stack_info_dict.setdefault(key, [])
        try:
            rds_client = boto3.client('rds')
            db_instance = rds_client.describe_db_instances(DBInstanceIdentifier=resourceid)
            db_size = "\t\t" + "Size:" + "\t" + db_instance['DBInstances'][0]['DBInstanceClass'] + "\n"
            db_storage = "\t\t" + "Capacity(GB):" + "\t" + str(db_instance['DBInstances'][0]['AllocatedStorage']) + "\n"
            db_storage_type = "\t\t" + "Storage Type:" + "\t" + db_instance['DBInstances'][0]['StorageType'] + "\n"
            db_arn = "\t\t" + "ARN:" + "\t" + db_instance['DBInstances'][0]['DBInstanceArn'] + "\n"
            db_cname = "\t\t" + "DNS Endpoint:" + "\t" + db_instance['DBInstances'][0]['Endpoint']['Address'] + "\n"
            db_version = "\t\t" + "MySQL Version:" + "\t" + db_instance['DBInstances'][0]['EngineVersion'] + "\n"
            stack_info_dict[key].append(
                resourceid + "\n" + db_size + db_storage + db_storage_type + db_arn + db_cname + db_version)

        except Exception as e:
            stack_info_dict[key].append("No resources could be found")
        return stack_info_dict
    elif "AutoScalingGroup" in resourcetype:
        key = "AutoScalingGroups"
        stack_info_dict.setdefault(key, [])
        try:
            as_client = boto3.client('autoscaling')
            instance_client = boto3.client('ec2')
            instance_resource = boto3.resource('ec2')
            as_group = as_client.describe_auto_scaling_groups(AutoScalingGroupNames=[resourceid])
            as_instance_list = "\t\t" + "Instances: "
            as_lc_name = "\t\t" + "LaunchConfig Name:" + "\t" + as_group['AutoScalingGroups'][0]['LaunchConfigurationName'] + "\n"
            as_minsize = "\t\t" + "Minimum Size:" + "\t" + str(as_group['AutoScalingGroups'][0]['MinSize']) + "\n"
            as_maxsize = "\t\t" + "Maximum Size:" + "\t" + str(as_group['AutoScalingGroups'][0]['MaxSize']) + "\n"
            if as_group['AutoScalingGroups'][0]['LoadBalancerNames']:
                as_lb = "\t\t" + "LoadBalancer Name:" + "\t" + as_group['AutoScalingGroups'][0]['LoadBalancerNames'][0] + "\n"
            else:
                as_lb = "\t\t" + "LoadBalancer:" + "\t" + "No LB attached" + "\n"
            lc_config = as_client.describe_launch_configurations(LaunchConfigurationNames=[as_group['AutoScalingGroups'][0]['LaunchConfigurationName']])

            for lc in lc_config['LaunchConfigurations']:
                as_iam = "\t\t" + "Instance IAM Role:" + "\t" + lc['IamInstanceProfile'] + "\n"
                as_key = "\t\t" + "SSH Key:" + "\t" + lc['KeyName'] + "\n"
                as_instance_type = "\t\t" + "Instance SIze:" + "\t" + lc['InstanceType'] + "\n"
                as_ami = "\t\t" + "AMI ID:" + "\t" + lc['ImageId'] + "\n"

            stack_info_dict[key].append(resourceid + "\n" + as_lc_name + as_minsize + as_maxsize + as_iam + as_key
                                        + as_instance_type + as_ami + as_lb + as_instance_list)

            as_instances = as_group['AutoScalingGroups'][0]['Instances']
            for instance in as_instances:
                instance_ip = instance_resource.Instance(instance['InstanceId']).private_ip_address
                instance_info = "\t\t" + instance['InstanceId'] + ":\t" + instance_ip + "\t" + \
                                instance['AvailabilityZone'] + "\t" + instance['LifecycleState']
                stack_info_dict[key].append(instance_info)

        except Exception as e:
            print e
        return stack_info_dict
    elif "SecurityGroup" in resourcetype:
        # Skip this info for now
        pass
    elif "ElasticLoadBalancing::LoadBalancer" in resourcetype:
        key = "Elastic Load Balancers"
        stack_info_dict.setdefault(key, [])
        try:
            elb_client = boto3.client('elb')
            lb_list = elb_client.describe_load_balancers(LoadBalancerNames=[resourceid])
            lb_name = "Name: " + lb_list['LoadBalancerDescriptions'][0]['LoadBalancerName']
            lb_dns_name = "DNS Name: " + lb_list['LoadBalancerDescriptions'][0]['DNSName']
            lb_health_check = "Health Check Target: " + lb_list['LoadBalancerDescriptions'][0]['HealthCheck']['Target']
            lb_scheme = "Scheme: " + lb_list['LoadBalancerDescriptions'][0]['Scheme']
            lb_instances = "Instances: " + str(lb_list['LoadBalancerDescriptions'][0]['Instances'])
            stack_info_dict[key].extend([lb_name, lb_dns_name, lb_health_check, lb_scheme, lb_instances])

        except Exception as e:
            print e
            pass
        return stack_info_dict

    elif "Instance" in resourcetype:
        key = "Instances"
        stack_info_dict.setdefault(key, [])
        try:
            instance_resource = boto3.resource('ec2')
            my_instance = instance_resource.Instance(resourceid)
            instance_ip = my_instance.private_ip_address
            for instance_tag in my_instance.tags:
                if 'Role' in instance_tag['Key']:
                    instance_name = instance_tag['Value']
            stack_info_dict[key].extend([resourceid + ": " + instance_ip + " " + instance_name])

        except Exception as e:
            print e
            pass
        return stack_info_dict


def status_progress(stack_name):
    stack_status = True
    t = 0
    click.echo("You can exit the program at any time and check the status in AWS console if you don't want to wait")

    while stack_status and t < 10:
        try:
            for stacks in client.describe_stacks(StackName=stack_name)['Stacks']:
                click.echo(stack_name + " status is: " + stacks['StackStatus'])
                if any(x in stacks['StackStatus'] for x in complete_status):
                    click.echo("We are done! Stack created successfully")
                    exit()
                if any(x in stacks['StackStatus'] for x in failed_status):
                    click.echo("Something went awfully wrong. Stack is rolling back")
                    for event in client.describe_stack_events(StackName=stack_name)['StackEvents']:
                        if any(x in event['ResourceStatus'] for x in failed_event):
                            reason = event['ResourceStatusReason']
                            break
                    click.echo("The error was: " + reason + " For more details check AWS console")
                    exit(1)
                time.sleep(30)
        except Exception as e:
            t += 1
            print "Couldn't find just created stack. Could be eventual consistency " \
                  "in AWS API. We'll retry a few more times"
            time.sleep(3)


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    pass


@click.command(context_settings=CONTEXT_SETTINGS, short_help='existing modules from which we can create a template')
def modules():
    """ Shows available modules for stacks that can be generated
    """
    for m in module_list:
        click.echo(m)


@click.command(context_settings=CONTEXT_SETTINGS)
def list():
    """ Shows existing stacks in AWS
    """
    stack_names = []
    paginator = client.get_paginator('list_stacks')
    for page in paginator.paginate(StackStatusFilter=complete_status):
        for s in page['StackSummaries']:
            stack_names.append(s['StackName'])

    for stack in sorted(stack_names, key=lambda z: z.lower()):
        click.echo(stack)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('stack_name', metavar='<stack_name>')
@click.option('--parameters', help='List of params in a format of "key=value,key1=value1". '
              'Values are case sensitive. Keys are not', metavar='<list>',
              default={}, type=BASE_DICT)
@click.option('--generator', help='Supplying this option will update the template for the stack from the given '
              'generator. If it has new parameters you need to supply them with the'
              ' --parameters flag', default=False)
def update(stack_name, parameters, generator):
    """ Updates a stack in AWS. Excepts to receive a stack name followed by
        one or more parameters to update
    """
    stack = StackParametersConfigObject(stack_name, parameters)

    if generator:
        stack.set_generator_parameters(generator)
        stack.set_generator_template(generator)
        stack.set_generator_capabilities(generator)

    stack.validate_input_parameters()
    stack.update_stack_parameters()
    update_stack(stack_name, stack)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('stack_name', metavar='<name>')
def delete(stack_name):
    """ Deletes a stack in AWS
    """
    if click.confirm('Are you sure you want to continue? This will permanently delete the stack '
                     'and resources that belong to it. Forever.'):
        client.delete_stack(StackName=stack_name)
        click.echo(stack_name + " is a goner")


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('stack_name', metavar='<name>')
def info(stack_name):
    """ Shows detailed information about a stack in AWS
    """
    try:
        stack = client.describe_stack_resources(StackName=stack_name)
        stack_info_output = {}
    except Exception as e:
        print "Looks like the stack name is not right or there was another error"
        exit(1)
    for resource in stack['StackResources']:
        stack_info(resource['ResourceType'], resource['PhysicalResourceId'], stack_info_output)
    for k, v in stack_info_output.iteritems():
        print k
        for z in v:
            print "\t" + z
    print "Parameters: " + "\t"
    params = get_stack_parameters(stack_name)
    for p in params:
        print p["ParameterKey"] + ":" + "\t" + p["ParameterValue"]


@click.command(context_settings=CONTEXT_SETTINGS, short_help='output CloudFormation JSON')
@click.argument('stack_name', metavar='<name>')
def show(stack_name):
    """
    \b
    Outputs CloudFormation JSON for the selected stack
    This can be saved and imported manually into Amazon's CloudFormation

    """
    try:
        module = module_import(stack_name)
        module.mystack.print_template()
    except Exception as e:
        print "The module name " + stack_name + " isn't valid or it contains an error"
        print e


@click.command(context_settings=CONTEXT_SETTINGS, short_help='upload CF template to AWS')
@click.argument('stack_name', metavar='<name>')
def upload(stack_name):
    """
    \b
    This will attempt to ask you for necessary parameters for the selected stack
    and automatically upload it to AWS CloudFormation. You need to have correct
    credentials for doing this action. This tool will attempt to find creds in:
    Environmental Variables (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)
    ~/.aws/credentials
    ~/.aws/config
    /etc/boto.cfg
    ~/.boto
    IAM role

    """
    stack_names = []
    stack_list = client.list_stacks(
        StackStatusFilter=CF_STATUS_FILTERS)
    for s in stack_list['StackSummaries']:
        stack_names.append(s['StackName'])
    module = module_import(stack_name)
    cf_parameters = []
    for p, z in sorted(module.mystack.template.parameters.iteritems()):
        default_value = None
        description = None
        for k, v in z.properties.iteritems():
            if 'Default' in k:
                default_value = v
            if 'Description' in k:
                description = v
            allowed = v if 'AllowedValues' in k else None
        if allowed:
            print default_value
            parameter_value = click.prompt(
                'Please put in the value for' + p + "\n" + "It must be selected from the following: " + str(
                    allowed) + "\n" + ":", default=default_value, type=str)
        else:
            parameter_value = click.prompt('Please put in the value for ' + p + ' (' + description + ')',
                                           default=default_value, type=str)
        if "DNSNAME".lower() in p.lower():
            __dns_validator(p, cf_parameters, parameter_value, default_value, description)

        if "DeploymentEnvironment".lower() in p.lower():
            env_value = parameter_value.lower()

        parameter_set = {'ParameterKey': p, 'ParameterValue': parameter_value}
        cf_parameters.append(parameter_set)

    app_value = module.mystack.config.get('apps', None)
    if app_value:
        app_name = app_value.keys()[0]
    else:
        app_name = stack_name

    default_stack_name = app_name.replace("_", "") + "-" + env_value
    stack_name = click.prompt('Please name your stack. You should accept the default unless you have a good reason '
                              'not to.', default=default_stack_name)
    if stack_name in stack_names:
        stack_name = click.prompt('The name ' + stack_name + " is already taken. Use something else")

    try:
        client.create_stack(StackName=stack_name, TemplateBody=str(module.mystack.template.to_json()),
                            Parameters=cf_parameters, Capabilities=module.mystack.capabilities)
        time.sleep(10)
    except Exception as e:
        print "Error in attempting to create the stack"
        print e
        exit(1)

    status_progress(stack_name)


@click.command(context_settings=CONTEXT_SETTINGS, short_help='deploy to an existing CF stack')
@click.argument('stack_name', metavar='<name>')
@click.argument('ami_id', metavar='<ami_id>')
def deploy(stack_name, ami_id):
    """
    \b
    This will deploy a new AMI to the stack. This command only works on stacks that
    have been designed to have their AMI updated. You need to specify the stack name as it exists in AWS and an ami ID.
    The tools will expect the stack to have an AMIID parameter.

    \b
    You need to have correct credentials for doing this action. This tool will attempt to find creds in:
    Environmental Variables (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)
    ~/.aws/credentials
    ~/.aws/config
    /etc/boto.cfg
    ~/.boto
    IAM role

    """
    try:
        stack_definition = client.describe_stacks(StackName=stack_name)['Stacks']
        for s in stack_definition:
            stack_parameters = s['Parameters']
    except Exception as e:
        print e
        exit(1)

    try:
        if next((item for item in stack_parameters if "AMIID".lower() in item["ParameterKey"].lower()), None) is None:
            raise AttributeError(
                'Error. Looks like the parameter AMIID is missing on this stack. It may not be deployable with AMIs.')
    except Exception as e:
        print e
        exit(1)

    for sp in stack_parameters:
        if "AMIID".lower() in sp["ParameterKey"].lower():
            sp["ParameterValue"] = ami_id
        else:
            sp.pop('ParameterValue')
            sp["UsePreviousValue"] = True

    try:
        client.update_stack(StackName=stack_name, UsePreviousTemplate=True, Parameters=stack_parameters)
    except ClientError as e:
        if 'No updates are to be performed' in e.response['Error']['Message']:
            print "Looks like you're trying to update the stack with the same AMI id that it's already running. " \
                  "That's not a valid operation"
            exit()
        else:
            print "Updating failed. Received error: %s" % e
            exit(1)
    status_progress(stack_name)


@click.command(context_settings=CONTEXT_SETTINGS, short_help='validate a module against AWS CF API')
@click.argument('stack_name', metavar='<name>')
def validate(stack_name):
    """
    \b
    Validates generated CloudFormation JSON for the selected module
    Provides a more accurate test than "show" command.

    """
    try:
        module = module_import(stack_name)

    except Exception as e:
        print "The module name " + stack_name + " isn't valid or it contains an error"
        print e
        exit(1)

    try:
        client.validate_template(TemplateBody=module.mystack.template.to_json())
        print "Module looks good!"
        exit(0)

    except Exception as e:
        print "Something is wrong with this module. See the error below"
        print e
        exit(-1)


cli.add_command(modules)
cli.add_command(show)
cli.add_command(upload)
cli.add_command(deploy)
cli.add_command(list)
cli.add_command(info)
cli.add_command(delete)
cli.add_command(validate)
cli.add_command(update)
