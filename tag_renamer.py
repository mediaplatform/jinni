import boto3

client = boto3.client('ec2')
tag_set = client.describe_tags()

for i in tag_set['Tags']:
    if 'env' in i['Key']:
        if 'Dev' in i['Value']:
            print i
            Response = client.create_tags(
                DryRun=False,
                Resources=[
                    i['ResourceId']
                ],
                Tags=[
                    {
                        'Key': i['Key'],
                        'Value': "DEV"
                    },
                ]
            )
