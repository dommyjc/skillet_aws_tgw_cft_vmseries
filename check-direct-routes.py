

import json
import re
import argparse
import boto3

#
# Initial constants
#
DEPLOYMENTDATA = 'deployment_data.json'
PARAMSFILE = './parameters.json'
TEMPLATEFILE = 'template.json'


def main():
    parser = argparse.ArgumentParser(description='Get Parameters')
    parser.add_argument('-k', '--aws_access_key', help='AWS Key', required=True)
    parser.add_argument('-s', '--aws_secret_key', help='AWS Secret', required=True)

    args = parser.parse_args()
    ACCESS_KEY = args.aws_access_key
    SECRET_KEY = args.aws_secret_key

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

    except Exception as e:
        print(e)



def _to_env(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).upper()


if __name__ == '__main__':

    main()