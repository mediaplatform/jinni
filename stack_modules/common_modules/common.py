import troposphere.ec2 as ec2
import troposphere.elasticloadbalancing as elb
import troposphere.elasticloadbalancingv2 as alb
import troposphere.elasticache as elasticache
import os
import yaml
import random
import alb
import collections
import copy
from string import Template as strTemplate
from troposphere import constants, ImportValue
from troposphere import FindInMap, GetAtt, Join, Ref, Tags, Template, rds, Base64, Sub, If
from troposphere.autoscaling import AutoScalingGroup, LaunchConfiguration
from troposphere.autoscaling import Tags as AsTags
from troposphere.policies import (AutoScalingRollingUpdate, AutoScalingReplacingUpdate,
                                  AutoScalingScheduledAction, UpdatePolicy, AutoScalingCreationPolicy,
                                  CreationPolicy, ResourceSignal)
from troposphere.route53 import RecordSetType
from troposphere.elasticsearch import Domain, EBSOptions
from troposphere.elasticsearch import ElasticsearchClusterConfig
from troposphere.elasticsearch import SnapshotOptions
import troposphere.kinesis as kinesis
from troposphere.cloudfront import Distribution, DistributionConfig
from troposphere.cloudfront import Origin, DefaultCacheBehavior, ViewerCertificate
from troposphere.cloudfront import ForwardedValues
from troposphere.cloudfront import S3Origin, CustomOrigin
from troposphere import Output
from troposphere import Parameter, Equals

# creating an override for templating here, with a custom delimiter.


class MyTemplate(strTemplate):
    delimiter = '$$'


class StackConfig(object):
    def __init__(self):

        self.localconfig = None
        self.availability_zones = []
        self.config = self.__loadglobalconfig('global.yml')

    def __loadglobalconfig(self, filename):
        mydir = os.path.dirname(os.path.abspath(__file__))
        relative_path = os.path.join(mydir, '..', "config")
        for loc in os.getcwd(), os.path.expanduser("~"), "/etc/stack_generator/", \
                   os.getcwd() + '/config', relative_path:
            try:
                with open(os.path.join(loc, filename), 'r') as f:
                    self.config = yaml.load(f)
            except IOError:
                pass
        try:
            self.config
            return self.config
        except Exception as e:
            print "Configuration file could not be found"
            exit()

    def loadlocalconfig(self, filename):
        mydir = os.path.dirname(os.path.abspath(__file__))
        relative_path = os.path.join(mydir, '..', "config")
        for loc in os.getcwd(), os.path.expanduser("~"), "/etc/stack_generator/", \
                   os.getcwd() + '/config', relative_path:
            try:
                with open(os.path.join(loc, filename), 'r') as f:
                    self.localconfig = yaml.load(f)
                    new_config = self.config.copy()
                    new_config.update(self.localconfig)
                    self.config = new_config
            except IOError:
                pass
        try:
            self.config
            return self.config
        except:
            print "Configuration file could not be found"
            exit()


class Stack(StackConfig):
    def __init__(self, stack_object):
        self.config = stack_object.config
        self.template = Template()
        self.sec_groups = self.__sec_groups_constructor()
        self.capabilities = []

    @staticmethod
    def __tag_role_generator(role, extra_roles):
        extra_tags = Tags(**{
            role: '',
        })
        if len(extra_roles) > 0:
            for i in extra_roles:
                extra_tags += Tags(**{
                    i: '',
                })
        return extra_tags

    # handle the case for references to static sec groups and also when they don't exist.
    def __sec_groups_constructor(self):
        default_sec_groups = []
        default_sec_groups.extend((ImportValue(self.config['monitoring_security_group_export_name']), ImportValue(self.config['admin_security_group_export_name'])))
        return default_sec_groups

    def __tag_elb_role_generator(self):
        role = self.config['apps'].values()[0].get("role", '')
        return Tags(Role=role, env=Ref("DeploymentEnvironment"))

    def __tag_as_role_generator(self, common_tags):

        copy_common_tags = copy.copy(common_tags)
        role = self.config['apps'].values()[0].get("role", '')
        extra_roles = self.config['apps'].values()[0].get("extra_roles", '')
        extra_tags = AsTags(**{
            role: '',
        })
        if len(extra_roles) > 0:
            for i in extra_roles:
                extra_tags += AsTags(**{
                    i: '',
                })

        other_tags = AsTags(Name=Ref("AWS::StackName"), Role=role)
        all_tags = extra_tags + other_tags + copy_common_tags
        return all_tags

    @staticmethod
    def __loaduserdata(filename, as_name):
        data = []
        mydir = os.path.dirname(os.path.abspath(__file__))
        relative_path = os.path.join(mydir, '..', "data")
        try:
            with open(os.path.join(relative_path, filename), 'r') as f:
                for line in f:
                    if line.strip('\n\r ') == '':
                        continue
                    # some funkiness below. Needs to substitute AS group name, since in a case of multiple groups
                    # can't rely on a static value.
                    line = MyTemplate(line)
                    line = line.substitute({'as_name': as_name})
                    line = Sub(line)
                    data.append(line)
        except IOError:
            print "User data file could not be found"
            exit()
        return Base64(Join('', data))

    def process_config(self, common_tags, default_size=None, alb_secgroups=None):
        # This function will be changed significantly once we start using the new_elb_
        # adder/target_adder function in favor of the classic ELB
        for k, v in self.config['apps'].iteritems():
            instance_list = []
            for index in xrange(v['count']):
                instance_list.append(self.instance_adder(k, v.get('size', default_size), v['ami_id'], v.get('role', k),
                                                         v.get('extra_roles', []), index, common_tags,
                                                         v.get('user_data', False)))
            if 'elb' in v:
                self.elb_adder(k, instance_list, Ref("Hostname"))
            if 'alb' in v:
                if alb_secgroups is None:
                    print "You need to pass a list of ALB Security Groups if alb is on"
                    quit()
                alb.Alb(self.template, self.config, instance_list, alb_secgroups)
                self.dns_adder(v.get("dns", None), "ApplicationLoadBalancer")

    def description(self, description, version='2010-09-09'):
        self.template.add_description(description)
        self.template.add_version(version)

    def print_template(self):
        output = self.template.to_json()
        print output

    def instance_adder(self, name, size, ami_id, role, extra_roles, index, common_tags, user_data_file=False):
        instance_sec_group = name + "group"
        instance_sec_group = instance_sec_group.translate(None, '_')
        instance_id = ''.join(ch for ch in name if ch.isalnum()) + str(index)
        instance = None
        extra_tags = self.__tag_role_generator(role, extra_roles)
        userdata = ""
        instance_name = Join("", [Ref("AWS::StackName"), str(index)])
        app_config = self.config['apps'].values()[0]
        if user_data_file:
            userdata = self.__loaduserdata(user_data_file)
        blockmap = self.__generate_blockmap()
        instance = self.template.add_resource(ec2.Instance(
            instance_id,
            ImageId=FindInMap("RegionMap", Ref("AWS::Region"), ami_id),
            KeyName=self.config['keyname'],
            Tags=common_tags + Tags(Name=instance_name, Role=role) + extra_tags,
            IamInstanceProfile=self.config['iam_role'],
            SecurityGroupIds=[Ref(instance_sec_group),
                              ImportValue(self.config['monitoring_security_group_export_name']),
                              ImportValue(self.config['admin_security_group_export_name'])],
            InstanceType=size,
            SubnetId=random.choice(self.config['subnets']),
            UserData=userdata,
            BlockDeviceMappings=blockmap
        ))
        if 'dns_host' in app_config and app_config['dns_host']:
            self.host_dns_adder(instance_name, instance_id)
        return instance

    def dns_adder(self, dns, elbid):
        dns_record_id = "DNS" + str(elbid)
        self.template.add_resource(RecordSetType(
            dns_record_id,
            HostedZoneName=Join("", [Ref("BaseURL"), "."]),
            Name=Join("", [dns, ".", Ref("BaseURL"), "."]),
            Type="CNAME",
            TTL="900",
            ResourceRecords=[GetAtt(elbid, "DNSName")],
        ))

    def host_dns_adder(self, dns, instanceid):
        dns_record_id = "DNS" + str(instanceid)
        self.template.add_resource(RecordSetType(
            dns_record_id,
            HostedZoneName=Join("", [Ref("BaseURL"), "."]),
            Name=Join("", [dns, ".", Ref("BaseURL"), "."]),
            Type="A",
            TTL="600",
            ResourceRecords=[GetAtt(instanceid, "PrivateIp")],  # PrivateIP PrivateDnsName
        ))

    def elb_adder(self, name, instance_list, dns):
        ports = self.config['apps'].values()[0].get("ports", None)
        elb_type = self.config['apps'].values()[0].get("type", 'internet-facing')
        elb_check_type = self.config['apps'].values()[0].get("elb_check_type", 'TCP')
        elb_check_path = self.config['apps'].values()[0].get("elb_check_path", "")

        if 'HTTP' in elb_check_type.upper() and not elb_check_path:
            elb_check_path = "/"

        if instance_list is None:
            instance_list = []
        elb_tags = self.__tag_elb_role_generator()
        elb_id = ''.join(ch for ch in name if ch.isalnum())
        elb_sec_group = name + "_group"
        elb_sec_group = elb_sec_group.translate(None, '_')
        elasticlb = self.template.add_resource(elb.LoadBalancer(
            elb_id,
            Subnets=self.config['public_subnets'],
            Scheme=elb_type,
            LoadBalancerName=Join("", [Ref("AWS::StackName"), '-', random.randint(1, 999)]),
            SecurityGroups=[Ref(elb_sec_group)],
            LBCookieStickinessPolicy=[
                elb.LBCookieStickinessPolicy(
                    PolicyName='LBCookeStickinessPolicy',
                )
            ],
            ConnectionDrainingPolicy=elb.ConnectionDrainingPolicy(
                Enabled=True,
                Timeout=300,
            ),
            CrossZone=True,
            Instances=[Ref(r) for r in instance_list],
            Tags=elb_tags
        ))

        elasticlb.Listeners = [
            elb.Listener(
                LoadBalancerPort="80",
                InstancePort=Ref("WebServerPort"),
                Protocol="HTTP",
                PolicyNames=['LBCookeStickinessPolicy']
            ),
            elb.Listener(
                LoadBalancerPort="443",
                InstancePort=Ref("WebServerPort"),
                Protocol="HTTPS",
                SSLCertificateId=Ref("CertName"),
                PolicyNames=['LBCookeStickinessPolicy'],
            )
        ]
        elasticlb.HealthCheck = elb.HealthCheck(Target=Join("", [elb_check_type.upper(), ":",
                                                                 ports, elb_check_path]), HealthyThreshold="3",
                                                UnhealthyThreshold="5", Interval="30",
                                                Timeout="5")
        if dns:
            self.dns_adder(dns, elb_id)
        return elasticlb

    def autoscaling_adder(self, common_tags, min_size, max_size, min_in_service, image_id, instance_size,
                          sec_groups, health_check_type='EC2', loadbalancer=False, keyname=None, targetgroup=False,
                          user_data_file=False):
        lc_name = "LaunchConfiguration" + str(random.randint(1, 999))
        as_name = "AutoScalingGroup" + str(random.randint(1, 999))
        if keyname is None:
            keyname = self.config['keyname']
        if user_data_file:
            userdata = self.__loaduserdata(user_data_file, as_name)
        else:
            userdata = self.__loaduserdata("default_userdata.txt", as_name)
        as_group_tags = self.__tag_as_role_generator(common_tags)
        blockmap = self.__generate_blockmap()
        lc_groups = copy.copy(self.sec_groups)
        lc_groups.append(Ref(sec_groups))
        launch_config = self.template.add_resource(
            LaunchConfiguration(
                lc_name,
                ImageId=image_id,
                KeyName=keyname,
                InstanceType=instance_size,
                SecurityGroups=lc_groups,
                IamInstanceProfile=self.config['iam_role'],
                UserData=userdata,
                BlockDeviceMappings=blockmap
            )
        )
        as_group = autoscalinggroup = AutoScalingGroup(
            as_name,
            Tags=as_group_tags,
            LaunchConfigurationName=Ref(lc_name),
            MinSize=Ref(min_size),
            MaxSize=Ref(max_size),
            VPCZoneIdentifier=self.config['subnets'],
            HealthCheckType=health_check_type,
            DependsOn=lc_name,
            CreationPolicy=CreationPolicy(
                AutoScalingCreationPolicy=AutoScalingCreationPolicy(
                    MinSuccessfulInstancesPercent=80
                ),
                ResourceSignal=ResourceSignal(
                    Count=1,
                    Timeout='PT10M'
                )
            ),
            UpdatePolicy=UpdatePolicy(
                AutoScalingReplacingUpdate=AutoScalingReplacingUpdate(
                    WillReplace=False,
                ),
                AutoScalingScheduledAction=AutoScalingScheduledAction(
                    IgnoreUnmodifiedGroupSizeProperties=True,
                ),
                AutoScalingRollingUpdate=AutoScalingRollingUpdate(
                    MaxBatchSize="2",
                    MinInstancesInService=Ref(min_in_service),
                    MinSuccessfulInstancesPercent=80,
                    PauseTime='PT10M',
                    WaitOnResourceSignals=True,
                    SuspendProcesses=["ReplaceUnHealthy, AZRebalance, AlarmNotifications, "
                                      "ScheduledActions, HealthCheck"]
                )
            )
        )
        if loadbalancer:
            autoscalinggroup.LoadBalancerNames = loadbalancer
        if targetgroup:
            autoscalinggroup.TargetGroupARNs = [targetgroup]
        self.template.add_resource(autoscalinggroup)
        # getting a litte funky below. Only reason is to be able to do overrides for k8s. Probably will need to be
        # revisited
        as_lc = collections.namedtuple('aslc', 'as_group,launch_config')(as_group, launch_config)
        return as_lc

    def rds_adder(self, instance_identifier, allocated_storage,
                  db_subnet_group, rds_group, db_size, db_name='MyDB',
                  storage_type='gp2', engine_version='5.5.40a',
                  storage_engine='MySQL', publicly_accessible=False):
        db_names = ''
        db_asf = (db_name.upper(), 'DNS')
        if publicly_accessible is False:
            publicly_accessible = "false"
        else:
            publicly_accessible = "true"

        dbinstance = rds.DBInstance(
            db_name,
            DBInstanceIdentifier=instance_identifier,
            Engine=storage_engine,
            EngineVersion=engine_version,
            MasterUsername=If("NotRestoringFromSnapshot", Ref("RDSDBUser"), Ref("AWS::NoValue")),
            MasterUserPassword=If("NotRestoringFromSnapshot", Ref("RDSDBPassword"), Ref("AWS::NoValue")),
            AllocatedStorage=allocated_storage,
            DBSnapshotIdentifier=If("NotRestoringFromSnapshot", Ref("AWS::NoValue"), Ref("RDSSnapshot")),
            StorageType=storage_type,
            DBSubnetGroupName=db_subnet_group,
            PubliclyAccessible=publicly_accessible,
            VPCSecurityGroups=rds_group,
            DBInstanceClass=db_size,
            StorageEncrypted=If("NotRestoringFromSnapshot", True, Ref("AWS::NoValue"))
        )
        dbdnsrecord = RecordSetType(
            db_names.join(db_asf),
            HostedZoneName=Join("", [Ref("RDSDNSDomain"), "."]),
            Name=Join("", [Ref("RDSDNSName"), ".", Ref("RDSDNSDomain"), "."]),
            Type="CNAME",
            TTL="900",
            ResourceRecords=[GetAtt(dbinstance, "Endpoint.Address")],
        )
        self.template.add_resource(dbinstance)
        self.template.add_resource(dbdnsrecord)

    # these are very similar functions below. One handles the general rules and another one handles self-refrencing ones.
    # this could be handled in one function, but would require some funky stuff around conditionals and use of AWS::NoValue.
    # it's a cleaner implementation this way.

    @staticmethod
    def rule_adder(fromport, toport=None, cidr='0.0.0.0/0', protocol='TCP', sourcegroupid=Ref("AWS::NoValue")):
        if toport is None:
            toport = fromport
        rule = ec2.SecurityGroupRule(
            IpProtocol=protocol,
            FromPort=fromport,
            ToPort=toport,
            CidrIp=cidr,
            SourceSecurityGroupId=sourcegroupid
        )
        return rule

    def rule_adder_self(self, group, fromport, toport=None, protocol='TCP'):
        """ This function exits to create self-referencing security groups. """
        if toport is None:
            toport = fromport
        rule = ec2.SecurityGroupIngress(
            "IngressRule",
            IpProtocol=protocol,
            FromPort=fromport,
            ToPort=toport,
            SourceSecurityGroupId=Ref(group),
            GroupId=Ref(group)
        )
        self.template.add_resource(rule)

    def group_adder(self, group_name, rules, description=None):
        group_tags = Tags(
            Name=group_name
        )
        if description is None:
            description = "Security Group for {0} Access".format(group_name)
        group = ec2.SecurityGroup(
            group_name,
            GroupDescription=description,
            SecurityGroupIngress=rules,
            VpcId=self.config['vpcid'],
            Tags=group_tags
        )
        self.template.add_resource(group)

    def redis_adder(self, name, tags, instance_type='cache.m3.medium', nodes=1, version='2.8.24'):
        rule = self.rule_adder(6379, cidr='10.0.0.0/16')
        subnetname = Join("", [name, Ref("DeploymentEnvironment")])
        self.group_adder("redissg", [rule])
        subnetgroup = self.template.add_resource(elasticache.SubnetGroup(
            "SubnetGroup",
            CacheSubnetGroupName=subnetname,
            Description='Subnet Group for ElasticCache Redis {0}'.format(name),
            SubnetIds=self.config['subnets']
        ))
        self.template.add_resource(elasticache.CacheCluster(
            "CacheCluster",
            ClusterName=name,
            Engine='redis',
            EngineVersion=version,
            CacheNodeType=instance_type,
            NumCacheNodes=nodes,
            Tags=tags,
            CacheSubnetGroupName=Ref(subnetgroup),
            VpcSecurityGroupIds=[GetAtt('redissg', "GroupId")],
        ))
        redisdnsrecord = RecordSetType(
            "RedisDNSRecord",
            HostedZoneName=Join("", [Ref("RedisDNSDomain"), "."]),
            Name=Join("", [Ref("RedisDNSName"), ".", Ref("RedisDNSDomain"), "."]),
            Type="CNAME",
            TTL="900",
            ResourceRecords=[GetAtt("CacheCluster", "RedisEndpoint.Address")],
        )
        self.template.add_resource(redisdnsrecord)

    def redis_adder_replcation(self, name, tags, instance_type='cache.m3.medium', cache_clusters=2, version='3.2.4'):
        rule = self.rule_adder(6379, cidr='10.0.0.0/16')
        subnetname = Join("", [name, Ref("DeploymentEnvironment")])
        self.group_adder("redissg", [rule])
        subnetgroup = self.template.add_resource(elasticache.SubnetGroup(
            "SubnetGroup",
            CacheSubnetGroupName=subnetname,
            Description='Subnet Group for ElasticCache Redis {0}'.format(name),
            SubnetIds=self.config['subnets']
        ))
        self.template.add_resource(elasticache.ReplicationGroup(
            'RedisReplicationGroup',
            ReplicationGroupId=name,
            Engine='redis',
            EngineVersion=version,
            CacheNodeType=instance_type,
            NumCacheClusters=cache_clusters,
            Tags=tags,
            CacheSubnetGroupName=Ref(subnetgroup),
            ReplicationGroupDescription="%s replication group" % name,
            SecurityGroupIds=[GetAtt('redissg', "GroupId")],
        ))
        redisdnsrecord = RecordSetType(
            "RedisDNSRecord",
            HostedZoneName=Join("", [Ref("RedisDNSDomain"), "."]),
            Name=Join("", [Ref("RedisDNSName"), ".", Ref("RedisDNSDomain"), "."]),
            Type="CNAME",
            TTL="900",
            ResourceRecords=[GetAtt("RedisReplicationGroup", "PrimaryEndPoint.Address")],
        )
        self.template.add_resource(redisdnsrecord)

    def elasticsearch_cluster(self, name, ebs=True, voltype='gp2'):
        es_domain = self.template.add_resource(Domain(
            name,
            DomainName=name + 'domain',
            ElasticsearchClusterConfig=ElasticsearchClusterConfig(
                DedicatedMasterEnabled=True,
                InstanceCount=2,
                ZoneAwarenessEnabled=True,
                InstanceType=constants.ELASTICSEARCH_M3_MEDIUM,
                DedicatedMasterType=constants.ELASTICSEARCH_M3_MEDIUM,
                DedicatedMasterCount=3
            ),
            EBSOptions=EBSOptions(EBSEnabled=ebs,
                                  Iops=0,
                                  VolumeSize=20,
                                  VolumeType=voltype),
            SnapshotOptions=SnapshotOptions(AutomatedSnapshotStartHour=0),
            AccessPolicies={'Version': '2012-10-17',
                            'Statement': [{
                                'Effect': 'Allow',
                                'Principal': {
                                    'AWS': '*'
                                },
                                'Action': 'es:*',
                                'Resource': '*'
                            }]},
            AdvancedOptions={"rest.action.multi.allow_explicit_index": "true"}
        ))
        return es_domain

    def kinesis_adder(self, name, shards):
        kinesis_stream = self.template.add_resource(kinesis.Stream(
            name,
            ShardCount=shards
        ))

        self.template.add_output([
            Output(
                "kinesisStreamName",
                Value=Ref(kinesis_stream),
            )
        ])

    def cloudfront_adder(self, static_site=True):
        origin_id = Join("", ["S3-", Ref("S3Name"), Ref("Path")])
        if static_site is True:
            origin = Origin(Id=origin_id, DomainName=Join("", [Ref("S3Name"), ".s3-website-us-east-1.amazonaws.com"]),
                            OriginPath=Ref("Path"), CustomOriginConfig=CustomOrigin(OriginProtocolPolicy="http-only"))
        else:
            origin = Origin(Id=origin_id, DomainName=Join("", [Ref("S3Name"), ".s3.amazonaws.com"]),
                            OriginPath=Ref("Path"), S3OriginConfig=S3Origin())
        myDistribution = self.template.add_resource(Distribution(
            "myDistribution",
            DistributionConfig=DistributionConfig(
                Origins=[origin],
                DefaultCacheBehavior=DefaultCacheBehavior(
                    TargetOriginId=origin_id,
                    ForwardedValues=ForwardedValues(
                        QueryString=False
                    ),
                    ViewerProtocolPolicy="redirect-to-https",
                    MinTTL=3600,
                    DefaultTTL=86400,
                    MaxTTL=31536000),
                ViewerCertificate=ViewerCertificate(
                    AcmCertificateArn=Ref("ACMarn"),
                    SslSupportMethod='sni-only'),
                Aliases=Ref("URLs"),
                DefaultRootObject=Ref("rootObject"),
                Enabled=True,
                HttpVersion='http2'
            )
        ))

        self.template.add_output([
            Output("DistributionId", Value=Ref(myDistribution)),
            Output("DistributionName", Value=Join("", ["http://", GetAtt(myDistribution, "DomainName")])),
        ])

    def __generate_blockmap(self, blockmap=None):
        if blockmap is None:
            blockmap = []
        blockmap = [
            ec2.BlockDeviceMapping(
                DeviceName="/dev/sda1",
                Ebs=ec2.EBSBlockDevice(
                    VolumeSize=Ref("RootVolSize"),
                    VolumeType="gp2"
                )
            ),
        ]
        app_config = self.config['apps'].values()[0]
        if 'mounts' in app_config:
            for mount in app_config['mounts']:
                blockmap.append(ec2.BlockDeviceMapping(DeviceName=mount['path'],
                                                       Ebs=ec2.EBSBlockDevice(
                                                           VolumeSize=Ref("{}VolSize".format(mount['name'])),
                                                           SnapshotId=If(
                                                               "{}NotRestoringFromSnapshot".format(mount['name']),
                                                               Ref("AWS::NoValue"),
                                                               Ref("{}SnapID".format(mount['name']))),
                                                           VolumeType=mount.get('type', 'standard'),
                                                           DeleteOnTermination=True)))
        return blockmap

    def disk_parameters(self):
        app_config = self.config['apps'].values()[0]
        if 'mounts' in app_config:  # If you want to be able to override Volume size set default to size of snapshot.
            for mount in app_config['mounts']:
                param = Parameter(
                    "{}VolSize".format(mount['name']),
                    Type="String",
                    Default=mount['size'],
                    Description="{} EBS Volume size.".format(mount['name'])
                )
                self.template.add_parameter(param)
                param = Parameter(
                    "{}SnapID".format(mount['name']),
                    Type="String",
                    Default=mount.get("SnapshotId", ""),
                    Description="{} EBS Volume Snapshot(Leave Blank to use new Volume).".format(mount['name'])
                )
                self.template.add_parameter(param)
                condition_name = "{}NotRestoringFromSnapshot".format(mount['name'])
                self.template.add_condition(condition_name, Equals(Ref("{}SnapID".format(mount['name'])), ""))
