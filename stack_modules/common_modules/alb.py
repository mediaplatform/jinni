import troposphere.elasticloadbalancingv2 as alb
from troposphere import Ref


class Alb:
    """ Constructor class for ALBs

    Only handles a very simple case and doesn't have callable methods or many parameters.
    Initialization of the class creates the necessary template.
    """
    def __init__(self, template, config, instance_list, sec_groups):
        self._instance_list = instance_list
        self._sec_groups = sec_groups
        self._config = config
        self._template = template
        # set a bunch of values needed to create an ALB
        self._protocol = 'HTTP'
        self._check_type = next(self.__key_finder('elb_check_type', self._config))
        self._check_path = next(self.__key_finder('elb_check_path', self._config))
        self._route_path = next(self.__key_finder('alb_route_path', self._config))
        self._ports = next(self.__key_finder('ports', self._config))
        self._path_targets = self.__target_generator(self._instance_list[:1])
        self._general_targets = self.__target_generator(self._instance_list[1:])
        # order can be important here. perhaps dependencies should be made more explicit.
        self.__create_alb()
        # Default pattern is to use a single (first) instance from the group as a destination for a path routing rule. Another group is the default path.
        self.__create_target_group(self._path_targets, "PathGroup")
        self.__create_target_group(self._general_targets, "GeneralGroup")
        self.__create_listeners()
        self.__create_rules("PathGroup")

    def __key_finder(self, key, config_dict):
        """ Small helper for backwards compatibility with existing configs"""
        if key in config_dict:
            yield config_dict[key]
        for k, v in config_dict.items():
            if isinstance(v, dict):
                for i in self.__key_finder(key, v):
                    yield i

    @staticmethod
    def __target_generator(instances):
        """ instance list for ALBs needs be in a "special" format. Assholes."""
        target_list = []
        for i in instances:
            target_list.append(alb.TargetDescription(Id=Ref(i)))
        return target_list

    def __create_alb(self):
        """ creates ALB. Some additional parameters are available on that object."""
        self._application_elb = self._template.add_resource(alb.LoadBalancer(
            "ApplicationLoadBalancer",
            Subnets=self._config['public_subnets'],
            SecurityGroups=self._sec_groups,
            Scheme="internet-facing" #default value
        ))

    def __create_target_group(self, instances, name):
        """ destination of where the traffic is going to go"""
        self._template.add_resource(alb.TargetGroup(
            name,
            HealthCheckProtocol=self._check_type,
            HealthCheckPath=self._check_path,
            HealthCheckPort=self._ports,
            Port=Ref("WebServerPort"),
            Protocol=self._check_type,
            Targets=instances,
            TargetGroupAttributes=[alb.TargetGroupAttribute(
                Key="stickiness.enabled",
                Value="true"
            )],
            VpcId=self._config['vpcid'],
            # bunch of default values below. Just making them explicit
            HealthCheckIntervalSeconds="30",
            HealthCheckTimeoutSeconds="5",
            HealthyThresholdCount="5",
            UnhealthyThresholdCount="2",
            Matcher=alb.Matcher(
                HttpCode="200")
        ))

    def __create_listeners(self):
        """ just assumes 80/443. Could be passed as a parameter.
        """
        self._template.add_resource(alb.Listener(
            "HTTPListener",
            Port=80,
            Protocol="HTTP",
            LoadBalancerArn=Ref(self._application_elb),
            DefaultActions=[alb.Action(
                Type='forward',
                TargetGroupArn=Ref("GeneralGroup")
            )]
        ))
        self._template.add_resource(alb.Listener(
            "HTTPSListener",
            Port=443,
            Protocol="HTTPS",
            Certificates=[alb.Certificate(
                CertificateArn=Ref("CertName")
                )],
            LoadBalancerArn=Ref(self._application_elb),
            DefaultActions=[alb.Action(
                Type='forward',
                TargetGroupArn=Ref("GeneralGroup")
            )]
        ))

    def __create_rules(self, group_name):
        """ lots of assumptions here. Only works with one rule.
         Assumes 80/443 Listener.
        """
        self._template.add_resource(alb.ListenerRule(
            "HTTPListenerRule",
            ListenerArn=Ref("HTTPListener"),
            Conditions=[alb.Condition(
                Field='path-pattern',
                Values=[self._route_path])],
            Actions=[alb.Action(
                Type='forward',
                TargetGroupArn=Ref(group_name)
            )],
            Priority="2"
        ))
        self._template.add_resource(alb.ListenerRule(
            "HTTPSListenerRule",
            ListenerArn=Ref("HTTPSListener"),
            Conditions=[alb.Condition(
                Field='path-pattern',
                Values=[self._route_path])],
            Actions=[alb.Action(
                Type='forward',
                TargetGroupArn=Ref(group_name)
            )],
            Priority="2"
        ))
