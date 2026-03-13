# aws_test.py - compatibility wrapper that wires split modules
import config
from certs_utils import resolve_cert_paths
import mqtt_client, publisher, subscriber

def apply_config_to_aws_test():
    # mqtt_client globals
    mqtt_client.AWS_ENDPOINT = getattr(config, "AWS_ENDPOINT", mqtt_client.AWS_ENDPOINT)
    mqtt_client.CLIENT_ID = getattr(config, "MQTT_CLIENT_ID", getattr(config, "DEVICE_ID", mqtt_client.CLIENT_ID))
    cert_file, key_file, root_ca = resolve_cert_paths(config)
    mqtt_client.CERT_FILE = cert_file
    mqtt_client.KEY_FILE = key_file
    mqtt_client.ROOT_CA = root_ca

    # publisher
    publisher.PUB_CLIENT_ID = mqtt_client.CLIENT_ID + "_pub"

    # subscriber
    subscriber.set_dedup_window(getattr(config, "DEDUP_WINDOW", 2))

    print("✅ aws_test: configuration applied")
