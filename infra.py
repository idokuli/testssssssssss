import boto3
import time
import sys

# --- STATIC CONFIGURATION ---
CONFIG = {
    'REGION': 'us-east-1',
    'VPC_CIDR': '10.50.0.0/16',
    'SN_A_CIDR': '10.50.1.0/24',
    'SN_B_CIDR': '10.50.2.0/24',
    'MY_AMI_ID': 'ami-0d5debe8444dbe950', # <--- Replace with your AMI ID
    'INSTANCE_TYPE': 't3.large',
    'PROJECT_TAG': 'S3HubSecureNLB'
}

def build_infra():
    ec2 = boto3.client('ec2', region_name=CONFIG['REGION'])
    asg = boto3.client('autoscaling', region_name=CONFIG['REGION'])
    elbv2 = boto3.client('elbv2', region_name=CONFIG['REGION'])

    print(f"🚀 Starting Full Build: NLB TCP:443 with HTTPS Health Check...")

    try:
        # 1. VPC Creation
        vpc = ec2.create_vpc(CidrBlock=CONFIG['VPC_CIDR'])['Vpc']
        vpc_id = vpc['VpcId']
        ec2.get_waiter('vpc_exists').wait(VpcIds=[vpc_id])
        ec2.create_tags(Resources=[vpc_id], Tags=[{'Key': 'Name', 'Value': f"{CONFIG['PROJECT_TAG']}-VPC"}])
        print(f"✅ VPC Created: {vpc_id}")

        # 2. Internet Gateway & Routing
        igw_id = ec2.create_internet_gateway()['InternetGateway']['InternetGatewayId']
        ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
        rt_id = ec2.create_route_table(VpcId=vpc_id)['RouteTable']['RouteTableId']
        ec2.create_route(RouteTableId=rt_id, DestinationCidrBlock='0.0.0.0/0', GatewayId=igw_id)

        # 3. Subnets
        sn_a = ec2.create_subnet(VpcId=vpc_id, CidrBlock=CONFIG['SN_A_CIDR'], AvailabilityZone=f"{CONFIG['REGION']}a")['Subnet']['SubnetId']
        sn_b = ec2.create_subnet(VpcId=vpc_id, CidrBlock=CONFIG['SN_B_CIDR'], AvailabilityZone=f"{CONFIG['REGION']}b")['Subnet']['SubnetId']
        ec2.associate_route_table(SubnetId=sn_a, RouteTableId=rt_id)
        ec2.associate_route_table(SubnetId=sn_b, RouteTableId=rt_id)
        print(f"✅ Subnets and Routing Configured")

        # 4. Security Group (Open 443 for both traffic and health checks)
        sg_id = ec2.create_security_group(GroupName=f"SG-{int(time.time())}", Description='NLB Port 443', VpcId=vpc_id)['GroupId']
        ec2.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=[
            {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])

        # 5. Target Group (TCP Routing + HTTPS Health Check)
        # HealthCheckProtocol MUST be HTTPS because your app uses ssl_context
        tg_arn = elbv2.create_target_group(
            Name=f"TG-{int(time.time())}"[:32], 
            Protocol='TCP', 
            Port=443, 
            VpcId=vpc_id, 
            TargetType='instance',
            HealthCheckProtocol='HTTPS',    # Verifies SSL Handshake
            HealthCheckPort='443',          # Checks app port
            HealthCheckPath='/health',      # Specific path you requested
            HealthCheckIntervalSeconds=30,
            HealthyThresholdCount=2,
            UnhealthyThresholdCount=2
        )['TargetGroups'][0]['TargetGroupArn']

        # 6. Network Load Balancer (NLB)
        nlb_data = elbv2.create_load_balancer(
            Name=f"NLB-{int(time.time())}"[:32], 
            Subnets=[sn_a, sn_b], 
            Type='network', 
            Scheme='internet-facing'
        )['LoadBalancers'][0]
        
        # 7. NLB Listener (TCP:443)
        # Pass-through: No SSL certificate needed on the NLB itself
        elbv2.create_listener(
            LoadBalancerArn=nlb_data['LoadBalancerArn'],
            Protocol='TCP', 
            Port=443,
            DefaultActions=[{'Type': 'forward', 'TargetGroupArn': tg_arn}]
        )

        # 8. Launch Template
        lt_name = f"LT-{int(time.time())}"
        ec2.create_launch_template(
            LaunchTemplateName=lt_name,
            LaunchTemplateData={
                'ImageId': CONFIG['MY_AMI_ID'],
                'InstanceType': CONFIG['INSTANCE_TYPE'],
                'NetworkInterfaces': [{'AssociatePublicIpAddress': True, 'DeviceIndex': 0, 'Groups': [sg_id]}]
            }
        )

        # 9. Auto Scaling Group
        asg_name = f"ASG-{int(time.time())}"
        asg.create_auto_scaling_group(
            AutoScalingGroupName=asg_name,
            LaunchTemplate={'LaunchTemplateName': lt_name, 'Version': '$Latest'},
            MinSize=2, MaxSize=6,DesiredCapacity=2, VPCZoneIdentifier=f"{sn_a},{sn_b}",
            TargetGroupARNs=[tg_arn]
        )

        print("\n" + "="*45)
        print("🎉 SUCCESS! NLB INFRASTRUCTURE IS LIVE")
        print(f"🔗 Public URL: https://{nlb_data['DNSName']}")
        print(f"💓 Health Monitoring: HTTPS://[Instance]:443/health")
        print("⚠️  Note: Use 'https://' in browser. Expect cert warnings.")
        print("="*45)

    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")

if __name__ == "__main__":
    # Sync clock for AWS auth
    import subprocess
    subprocess.run(["sudo", "chronyc", "-a", "makestep"], capture_output=True)
    build_infra()