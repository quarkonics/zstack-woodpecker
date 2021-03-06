import apibinding.inventory as inventory
import zstackwoodpecker.header.header as zstack_header

RUNNING = inventory.RUNNING
STOPPED = inventory.STOPPED
DESTROYED = inventory.DESTROYED
EXPUNGED = 'EXPUNGED'

VOLUME_BANDWIDTH = 'volumeTotalBandwidth'
VOLUME_IOPS = 'volumeTotalIops'
NETWORK_OUTBOUND_BANDWIDTH = 'networkOutboundBandwidth'

class TestVm(zstack_header.ZstackObject):

    def __init__(self):
        self.vm = None
        self.state = None
        self.delete_policy = None
        self.delete_delay_time = None

    def __repr__(self):
        if self.vm:
            return '%s-%s' % (self.__class__.__name__, self.vm.uuid)
        return '%s-None' % self.__class__.__name__

    def create(self):
        self.state = RUNNING

    def destroy(self):
        if self.delete_policy != zstack_header.DELETE_DIRECT:
            self.state = DESTROYED
        else:
            self.state = EXPUNGED

    def start(self):
        self.state = RUNNING

    def stop(self):
        self.state = STOPPED

    def reboot(self):
        self.state = RUNNING

    def migrate(self, target_host):
        pass

    def check(self):
        pass

    def expunge(self):
        self.state = EXPUNGED

    def get_vm(self):
        return self.vm

    def get_state(self):
        return self.state

    def set_state(self, state):
        self.state = state

    def update(self):
        pass

    def set_delete_policy(self, policy):
        self.delete_policy = policy

    def get_delete_policy(self):
        return self.delete_policy

    def set_delete_delay_time(self, time):
        self.delete_delay_time = time

    def get_delete_delay_time(self):
        return self.delete_delay_time
