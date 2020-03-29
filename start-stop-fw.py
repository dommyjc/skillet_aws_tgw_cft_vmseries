import argparse
import json
import logging
import time

import boto3


logger = logging.getLogger()
logger.setLevel(logging.INFO)

aws_region = ''
ACCESS_KEY = ''
SECRET_KEY = ''


#
# Initial constants
#
DEPLOYMENTDATA = './deployment_data.json'
PARAMSFILE = './parameters.json'
TEMPLATEFILE = 'template.json'

def check_route_table():
    try:
        with open(DEPLOYMENTDATA, 'r') as data:
            config_dict = json.load(data)
            stack_name = config_dict['stack_name']
            s3bucket_name = config_dict['s3bucket_name']
            aws_region =  config_dict['aws_region']
    except FileNotFoundError:
        print('File no longer exists')

    cf = boto3.client('cloudformation', region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)
    ec2_client = boto3.client('ec2', region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)
    r = cf.describe_stacks(StackName=stack_name)

    stack, = r['Stacks']
    outputs = stack['Outputs']
    fwints = {}
    out = {}
    for o in outputs:
        key = o['OutputKey']
        out[key] = o['OutputValue']
        if o['OutputKey'] == 'FW1TrustNetworkInterface' or o['OutputKey'] == 'FW2TrustNetworkInterface':
            intkey = o['OutputValue']
            fwints[intkey] =o['Description']

    route_table_id = out['fromTGWRouteTableId']

    try:
        resp_rt_table = ec2_client.describe_route_tables(RouteTableIds=[route_table_id])
        routes =  resp_rt_table['RouteTables'][0]['Routes']
        print('\n{:25}{:30}{:20}\n'.format('Destination Prefix', 'Next Hop', 'Description'))
        for route in routes:
            nh = ''
            desc = ''
            if 'NetworkInterfaceId' in route.keys():
                nh = route['NetworkInterfaceId']
                desc = fwints[nh]
            elif 'GatewayId' in route.keys():
                nh = route['GatewayId']
            print('{:25}{:30}{:20}'.format(route['DestinationCidrBlock'], nh, desc))
        print('\n')
    except Exception as e:
        print(e)


def run_lambda(function_name, invocation_type = 'Event'):
    lambda_client = boto3.client('lambda', region_name=aws_region,
                              aws_access_key_id=ACCESS_KEY,
                              aws_secret_access_key=SECRET_KEY)
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType=invocation_type,

    )
    time.sleep(10)
    return response


def stop_firewall(fw_instance_id):
    ec2_client = boto3.client('ec2', region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)
    result = ec2_client.stop_instances(InstanceIds=[fw_instance_id])
    return


def start_firewall(fw_instance_id):
    ec2_client = boto3.client('ec2', region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)
    result = ec2_client.start_instances(InstanceIds=[fw_instance_id])
    return


def update_env_variable(function, key, value):
    lambda_client = boto3.client('lambda', region_name=aws_region,
                              aws_access_key_id=ACCESS_KEY,
                              aws_secret_access_key=SECRET_KEY)
    try:
        function_data = lambda_client.get_function_configuration(FunctionName=function)
        env_variables = function_data['Environment']['Variables']
    except Exception as e:
        print('Error getting lambda function details {}'.format(function))

    env_variables.update({key: value})

    try:
        response = lambda_client.update_function_configuration(
            FunctionName=function,
            Environment={
                'Variables': env_variables}
        )
    except Exception as e:
        print('Error {}'.format(e))
    return


def main():
    global ACCESS_KEY
    global SECRET_KEY
    global aws_region


    parser = argparse.ArgumentParser(description='Get Parameters')
    parser.add_argument('-p', '--preempt', help='Preempt', default='yes')
    parser.add_argument('-f', '--firewall', help='Firewall to start/stop')
    parser.add_argument('-a', '--action', help='Firewall to start/stop', default='start')
    parser.add_argument('-r', '--split_routes', help='Split routes', default='yes')
    parser.add_argument('-k', '--aws_access_key', help='AWS Key', required=True)
    parser.add_argument('-s', '--aws_secret_key', help='AWS Secret', required=True)

    args = parser.parse_args()
    ACCESS_KEY = args.aws_access_key
    SECRET_KEY = args.aws_secret_key
    split_routes = args.split_routes
    preempt = args.preempt
    firewall_to_change = args.firewall
    fw_action = args.action

    # Read stack data from file
    # deploy stores data in config_dict
    #
    # config_dict = {
    #     's3bucket_name': s3bucket_name,
    #     'stack_name': stack_name
    # }

    try:
        with open(DEPLOYMENTDATA, 'r') as data:
            stack_data = json.load(data)
            stack = stack_data['stack_name']
            aws_region = stack_data['aws_region']
            route_table_id =  stack_data['fromTGWRouteTableId']
            lambda_function = stack_data['LambdaFunctionName']


    except Exception as e:
        print('Could not open file {} to find stack info'.format(DEPLOYMENTDATA))

    if stack:
        cf_client = boto3.client('cloudformation', region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)
        ec2_client = boto3.client('ec2', region_name=aws_region,
                             aws_access_key_id=ACCESS_KEY,
                             aws_secret_access_key=SECRET_KEY)
        
        r = cf_client.describe_stacks(StackName=stack)
        stack, = r['Stacks']
        outputs = stack['Outputs']
        fwinstances = {}
        out = {}
        for o in outputs:
            key = o['OutputKey']
            out[key] = o['OutputValue']

    fw1_instance_id = out['Fw1InstanceId']
    fw2_instance_id = out['Fw2InstanceId']
    lambda_function = out['LambdaFunctionName']

    try:
        fw1_instance_data = ec2_client.describe_instances(
            InstanceIds=[fw1_instance_id]
        )

        fw2_instance_data = ec2_client.describe_instances(
            InstanceIds=[fw2_instance_id]
        )

    except Exception as e:
        print('Error {}'.format(e))
    # print_header = '#########################################'

    # Setup lambda environment variables for next run
    # print('{:^80}\n'.format(print_header))
    print('{:^80}\n'.format('****** Setting Environment Variables ********'))
    update_env_variable(lambda_function, 'splitroutes', split_routes)
    print('{:^80}\n'.format('****** Setting splitroutes variable to ' + split_routes + ' ********'))
    update_env_variable(lambda_function, 'preempt', preempt)
    print('{:^80}\n'.format('****** Setting preempt variable to ' + preempt + ' ********'))

    # Perform Firewall Action
    # print('{:^80}\n'.format(print_header))
    # print('{:^80}\n'.format('Checking start/stop action for ' + firewall_to_change))
    # print('{:^80}\n'.format('Action ' + fw_action))
    # print('{:^80}\n'.format(print_header))


    if firewall_to_change == 'Firewall2':
        firewall_id = fw2_instance_id
    else:
        firewall_id = fw1_instance_id
    fw_data = ec2_client.describe_instances(
        InstanceIds=[firewall_id]
    )
    fwstate = fw_data['Reservations'][0]['Instances'][0]['State']['Name']
    if fw_action == 'stop' and fwstate == 'running':
        stop_firewall(firewall_id)
        print('{:^80}\n'.format('****** Sending Command "stop" to firewall ********'))
        # print('{:^80}\n'.format('Check the route table after the action completes'))
        # print('{:^80}\n'.format(print_header))

    elif fwstate == 'stopped' and fw_action == 'start':
        start_firewall(firewall_id)
        print('{:^80}\n'.format('****** Sending Command "start" to firewall ********'))
        print('{:^80}\n'.format('****** If preempt is set to "yes" the route table will be modified ********'))
        print('{:^80}\n'.format('****** Waiting for 3 mins for firewall to start ******** ********'))
        print
        time.sleep(180)
    else:
        # print('{:^80}\n'.format(print_header))
        print('{:^80}\n'.format(firewall_to_change + ' is in a ' + fwstate + ' state. Nothing to do to the firewalls'))
        # print('{:^80}\n'.format(print_header))

    print('{:^80}\n'.format('****** Route table before lambda execution ********'))
    check_route_table()
    print('{:^80}\n'.format('****** Running lambda function ********'))
    print('{:^80}\n'.format('****** Route table after lambda execution ********'))
    run_lambda(lambda_function)
    check_route_table()

    # Get new route table


if __name__ == '__main__':
    main()
