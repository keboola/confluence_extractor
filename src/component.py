import csv
import logging
from datetime import datetime

from keboola.component.base import ComponentBase
from keboola.component.exceptions import UserException

from client.confluence_client import ConfluenceClient, ConfluenceClientException

# configuration variables
KEY_USERNAME = 'username'
KEY_URL = 'url'
KEY_API_TOKEN = '#api_token'
KEY_BEAUTIFY = 'beautify'
KEY_INCREMENTAL = 'incremental'
KEY_GROUP_DESTINATION_OPTIONS = 'destination_options'

REQUIRED_PARAMETERS = [KEY_USERNAME, KEY_URL, KEY_API_TOKEN]


class Component(ComponentBase):

    def __init__(self):
        super().__init__()
        self.current_time = datetime.utcnow()
        self.last_run = "2000-01-01T00:00:00.000Z"

    def run(self):
        self.validate_configuration_parameters(REQUIRED_PARAMETERS)
        url, username, token, beautify, incremental = self._init_parameters()
        self.setup_last_run(incremental)

        table_out = self.create_out_table_definition("confluence_pages", primary_key=["id"], incremental=incremental)
        client = ConfluenceClient(url, username, token)

        self.write_confluence_data(client, beautify, table_out)

        self.write_manifest(table_out)
        self.write_state_file({"last_run": self.current_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'})
        logging.info(f"The component has fetched {client.fetched_total} new Confluence documents.")

    def _init_parameters(self):
        params = self.configuration.parameters
        url = params.get(KEY_URL)
        username = params.get(KEY_USERNAME)
        token = params.get(KEY_API_TOKEN)
        destination_options = params.get(KEY_GROUP_DESTINATION_OPTIONS, {})
        beautify = destination_options.get(KEY_BEAUTIFY, False)
        incremental = destination_options.get(KEY_INCREMENTAL, False)
        return url, username, token, beautify, incremental

    def setup_last_run(self, incremental):
        if incremental:
            statefile = self.get_state_file()
            if statefile.get("last_run"):
                self.last_run = statefile.get("last_run")
                logging.info(f"Using last_run from statefile: {self.last_run}")
            else:
                logging.info(f"No last_run found in statefile, using default timestamp: {self.last_run}")

    def write_confluence_data(self, client, beautify, table_out):
        fieldnames = ["id", "created_date", "last_updated_date", "title", "creator", "last_modifier", "url", "space",
                      "text"]
        with open(table_out.full_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            try:
                for page in client.get_confluence_pages(timestamp_from=self.last_run, beautify=beautify):
                    writer.writerow(page)
            except ConfluenceClientException as e:
                raise UserException(f"Cannot fetch data from Confluence, error: {e}")


"""
        Main entrypoint
"""
if __name__ == "__main__":
    try:
        comp = Component()
        # this triggers the run method by default and is controlled by the configuration.action parameter
        comp.execute_action()
    except UserException as exc:
        logging.exception(exc)
        exit(1)
    except Exception as exc:
        logging.exception(exc)
        exit(2)
