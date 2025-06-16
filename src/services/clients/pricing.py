import boto3

class PricingClient:
    def __init__(self):
        self.client = boto3.client('pricing', region_name='us-east-1')

    def list_region_os_prices(self, operating_system: str, region: str):
        paginator = self.client.get_paginator('get_products')

        pages = paginator.paginate(ServiceCode='AmazonEC2', Filters=[
            {'Type': 'TERM_MATCH', 'Field': 'operatingSystem',
             'Value': operating_system},
            {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
            {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
            {'Type': 'TERM_MATCH', 'Field': 'regionCode',
             'Value': region},
            {'Type': 'TERM_MATCH', 'Field': 'capacityStatus', 'Value': 'Used'},
            {'Type': 'TERM_MATCH', 'Field': 'serviceCode',
             'Value': 'AmazonEC2'},
            {'Type': 'TERM_MATCH', 'Field': 'licenseModel',
             'Value': 'No License required'},
        ])
        entries = []
        for page in pages:
            entries.extend(page['PriceList'])
        return entries
