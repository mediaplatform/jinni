from troposphere import Parameter
from troposphere import Tags, Ref
from troposphere.autoscaling import Tags as AsTags

common_tags = Tags(
    env=Ref("DeploymentEnvironment"),
    Version=Ref("ProductVersion"),
    Product=Ref("Product"),
    prometheus_node="yes"
)
common_tags_as = AsTags(
    env=Ref("DeploymentEnvironment"),
    Version=Ref("ProductVersion"),
    Product=Ref("Product"),
    prometheus_node="yes"
)

basic_parameters_non_as = {
    "env": Parameter(
        "DeploymentEnvironment",
        Type="String",
        Default="DEV",
        Description="Environment you are building",
    ),
    "ver": Parameter(
        "ProductVersion",
        Type="String",
        Default="6.1",
        Description="Version deploying (e.g. 6.1)",
    ),
    "root_device_size": Parameter(
        "RootVolSize",
        Type="String",
        Default="8",
        Description="Default root volume size for the instance. Typically should stay at default",
    ),
    "product": Parameter(
        "Product",
        Type="String",
        Default="PT",
        Description="The product that is being deployed"
    ),
    "ssh_key": Parameter(
        "SSHKeyName",
        Type="String",
        Default="ivtec2dev",
        Description="SSH key to use for ec2 instances",
        AllowedValues=[
            "ivtec2dev",
            "ivtec2qa",
            "ivtec2admin"
        ],
        ConstraintDescription="must select a valid existing key",
    ),
}

elb_parameters_non_as = {
    "webport": Parameter(
        "WebServerPort",
        Type="String",
        Default="80",
        Description="TCP/IP port of the web server",
    ),
    "base_url": Parameter(
        "BaseURL",
        Type="String",
        Default="mediaplatformdev.com",
        Description="This is the base URL for the environment"
    ),
    "cert_name": Parameter(
        "CertName",
        Type="String",
        Default="arn:aws:iam::314826648217:server-certificate/AllDomainsAllThingsOct2018",
        Description="This cert should work for everything. Usually to be left at default",
    )
}

basic_parameters = {
    "env": Parameter(
        "DeploymentEnvironment",
        Type="String",
        Default="DEV",
        Description="Environment you are building",
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
        Default="Transcoder",
        Description="The product that is being deployed"
    ),
    "ssh_key": Parameter(
        "SSHKeyName",
        Type="String",
        Default="ivtec2dev",
        Description="SSH key to use for ec2 instances",
        AllowedValues=[
            "ivtec2dev",
            "ivtec2qa",
            "ivtec2prod",
            "ivtec2admin"
        ],
        ConstraintDescription="must select a valid existing key",
    ),
    "root_device_size": Parameter(
        "RootVolSize",
        Type="String",
        Default="8",
        Description="Default root volume size for the instance. Typically should stay at default",
    ),
    "instance_type": Parameter(
        "InstanceType",
        Type="String",
        Description="The instance type that you want",
        Default="t2.medium",
        AllowedValues=[
            "t2.small",
            "t2.medium",
            "t2.large",
            "t2.xlarge",
            "t2.2xlarge",
            "m4.large",
            "m4.xlarge",
            "c4.large",
            "c4.xlarge"
        ],
        ConstraintDescription="Please select one of the instance types",
    ),
    "ami_id": Parameter(
        "AMIID",
        Type="String",
        Description="The AMI ID for your instances. For PT app you should locate the latest AMI with the role of transcoder-core-scripts",
        Default="ami-fd88f387"
    ),
}
asg_parameters = {
    "min_desired": Parameter(
        "InitCapacity",
        Default="1",
        Type="String",
        Description="Min number of servers to run",
    ),
    "max_desired": Parameter(
        "MaxCapacity",
        Default="2",
        Type="String",
        Description="Max number of servers allowed",
    ),
    "min_in_service": Parameter(
        "MinInService",
        Default="1",
        Type="String",
        Description="This value controls the deployment process to AS group. "
                    "This number should always be less than MaxSize of the AS group."
    ),
}
elb_parameters = {
    "webport": Parameter(
        "WebServerPort",
        Type="String",
        Default="80",
        Description="TCP/IP port of the web server. This is the port on which the ELB will forward traffic. In some cases the correct answer is 8080 (transcoder) or 8983 (solr)",
    ),
    "base_url": Parameter(
        "BaseURL",
        Type="String",
        Default="mediaplatformdev.com",
        Description="This is the base URL for the environment"
    ),
    "base_url_hostname": Parameter(
        "Hostname",
        Type="String",
        Description="This is the URL subdomain through which the instances will be accessed via the ELB.  This should not already exist in Route 53"
    ),
    "cert_name": Parameter(
        "CertName",
        Type="String",
        Default="arn:aws:iam::314826648217:server-certificate/AllDomainsAllThingsOct2018",
        Description="Should work for all environments",
    )
}
redis_parameters = {
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
    "name": Parameter(
        "RedisName",
        Type="String",
        Description="Name of Redis Cluster",
    ),
    "redis_dns_domain": Parameter(
        "RedisDNSDomain",
        Type="String",
        Default="mediaplatformdev.com",
        Description="This is the base URL domain through which redis can be accessed. This should already exist in Route 53"
    ),
    "redis_dns_name": Parameter(
        "RedisDNSName",
        Type="String",
        Default="redisdb",
        Description="This is an easy to remember CNAME for Redis instance-- the URL subdomain through which the instance will be accessed. This should not already exist in Route 53"
    )
}
redis_parameters_shared = {
    "redis_instance_type": Parameter(
        "RedisSize",
        Type="String",
        Default="cache.m3.medium",
        AllowedValues=[
            "cache.m3.small", "cache.m3.medium", "cache.r3.large", "cache.m2.xlarge", "cache.m3.2xlarge"],
        Description="Database Instance Class"
    ),
    "redis_dns_domain": Parameter(
        "RedisDNSDomain",
        Type="String",
        Default="mediaplatformdev.com",
        Description="This is the base URL domain through which redis can be accessed. This should already exist in Route 53"
    ),
    "redis_dns_name": Parameter(
        "RedisDNSName",
        Type="String",
        Default="redisdb",
        Description="This is an easy to remember CNAME for Redis instance-- the URL subdomain through which the instance will be accessed. This should not already exist in Route 53"
    )
}
rds_parameters = {
    "env": Parameter(
        "DeploymentEnvironment",
        Type="String",
        Default="DEV",
        Description="Environment you are building (DEV,QA,STG,PROD)",
    ),
    "rds_snapshot_name": Parameter(
        "RDSSnapshot",
        Type="String",
        Default="",
        Description="This is the name of the snapshot to be restored. You have to search for it in the RDS --> "
                    "Snapshots area. It will look something like rds:<name><date>"
    ),
    "rds_db_size": Parameter(
        "RDSDBSize",
        Type="String",
        Default="db.m3.medium",
        AllowedValues=[
            "db.m1.small", "db.m3.medium", "db.m1.large", "db.m2.xlarge", "db.m3.2xlarge"],
        Description="Database Instance Class"
    ),
    "rds_db_user": Parameter(
        "RDSDBUser",
        Type="String",
        Description="DB Username. Only used if you're not restoring from an image",
        MaxLength="16",
        Default="root"
    ),
    "rds_db_password": Parameter(
        "RDSDBPassword",
        NoEcho=True,
        Description="The database admin account password. Only used if you're not restoring from an image",
        Type="String",
        MaxLength="41",
    ),
    "rds_db_allocated": Parameter(
        "RDSDBAllocatedStorage",
        Description="Keep blank if restoring from snapshot. The size of the database (Gb)",
        Default="10",
        Type="Number",
        MaxValue="1024",
        ConstraintDescription="must be between 5 and 1024Gb."
    ),
    "rds_db_name": Parameter(
        "RDSDBName",
        Type="String",
        Default="transcoder-db-dev",
        Description="The Instance identifier of the database. Must be unique across RDS instances."
    ),
    "rds_subnet_group": Parameter(
        "RDSDBSubnetGroup",
        Type="String",
        Default="mpinternalvpcsubnetgroup",
        Description="This should probably not change, unless you know specifically what you're looking for. "
    ),
    "rds_dns_domain": Parameter(
        "RDSDNSDomain",
        Type="String",
        Default="mediaplatformdev.com",
        Description="This is the base URL domain through which the instance can be accessed. This should already exist in Route 53"
    ),
    "rds_dns_name": Parameter(
        "RDSDNSName",
        Type="String",
        Description="This is an easy to remember CNAME for the RDS instance-- the URL subdomain through which the instance will be accessed.  This should not already exist in Route 53"
    ),
}
