'''
zstack vm test class

@author: Youyk
'''
import zstackwoodpecker.header.header as zstack_header
import zstackwoodpecker.header.vm as vm_header
import zstackwoodpecker.operations.vm_operations as vm_ops
import zstackwoodpecker.operations.net_operations as net_ops
import zstackwoodpecker.operations.resource_operations as res_ops
import zstackwoodpecker.operations.tag_operations as tag_ops
import zstackwoodpecker.test_util as test_util
import zstackwoodpecker.test_lib as test_lib

class ZstackTestVm(vm_header.TestVm):
    def __init__(self):
        super(ZstackTestVm, self).__init__()
        self.vm_creation_option = test_util.VmOption()
        self.changed_instance_offering_uuid = None
        self.delete_policy = test_lib.lib_get_delete_policy('vm')
        self.delete_delay_time = test_lib.lib_get_expunge_time('vm')

    def __hash__(self):
        return hash(self.vm.uuid)

    def __eq__(self, other):
        return self.vm.uuid == other.vm.uuid

    def change_instance_offering(self, new_instance_offering_uuid, \
            session_uuid = None):
        if self.state != vm_header.STOPPED:
            test_util.test_logger('VM: %s state %s is not %s. Can not change template' % self.vm.get_vm().uuid, self.state, vm_header.STOPPED)
            return False

        vm_uuid = self.get_vm().uuid
        vm_ops.change_instance_offering(vm_uuid, \
                new_instance_offering_uuid, session_uuid)
        self.changed_instance_offering_uuid = new_instance_offering_uuid

        ##in current design, QoS changing need to manually change vm system tag.
        #cond = res_ops.gen_query_conditions('resourceUuid', '=', \
        #        new_instance_offering_uuid)
        #new_system_tags = res_ops.query_resource(res_ops.SYSTEM_TAG, cond)
        #cond_vm = res_ops.gen_query_conditions('resourceUuid', '=', \
        #        vm_uuid)
        #for tag in new_system_tags:
        #    if vm_header.VOLUME_IOPS in tag.tag or \
        #            vm_header.VOLUME_BANDWIDTH in tag.tag or \
        #            vm_header.NETWORK_OUTBOUND_BANDWIDTH in tag.tag:
        #        tag_name = tag.tag.split('::')[0]
        #        cond_vm = res_ops.gen_query_conditions('tag', 'like', \
        #                tag_name, cond_vm)
        #        old_system_tags = res_ops.query_resource(res_ops.SYSTEM_TAG, \
        #                cond_vm)
        #        for old_tag in old_system_tags:
        #            tag_ops.delete_tag(old_tag.uuid)
        #        tag_ops.create_system_tag('VmInstanceVO', \
        #                vm_uuid, tag.tag)

    def get_instance_offering_uuid(self):
        if not self.changed_instance_offering_uuid:
            return self.get_creation_option().get_instance_offering_uuid()

        return self.change_instance_offering_uuid

    def create(self):
        self.vm = vm_ops.create_vm(self.vm_creation_option)
        super(ZstackTestVm, self).create()

    def destroy(self, session_uuid = None):
        vm_ops.destroy_vm(self.vm.uuid, session_uuid)
        super(ZstackTestVm, self).destroy()

    def start(self, session_uuid = None):
        self.vm = vm_ops.start_vm(self.vm.uuid, session_uuid)
        super(ZstackTestVm, self).start()

    def stop(self, session_uuid = None):
        self.vm = vm_ops.stop_vm(self.vm.uuid, session_uuid)
        super(ZstackTestVm, self).stop()

    def reboot(self, session_uuid = None):
        self.vm = vm_ops.reboot_vm(self.vm.uuid, session_uuid)
        super(ZstackTestVm, self).reboot()

    def migrate(self, host_uuid, timeout = None, session_uuid = None):
        self.vm = vm_ops.migrate_vm(self.vm.uuid, host_uuid, timeout,\
                session_uuid)
        super(ZstackTestVm, self).migrate(host_uuid)

    def expunge(self, session_uuid = None):
        vm_ops.expunge_vm(self.vm.uuid, session_uuid)
        super(ZstackTestVm, self).expunge()

    def clean(self):
        if self.delete_policy != zstack_header.DELETE_DIRECT:
            if self.get_state() == vm_header.DESTROYED:
                self.expunge()
            elif self.get_state() == vm_header.EXPUNGED:
                pass
            else:
                self.destroy()
                self.expunge()
        else:
            self.destroy()

    def check(self):
        import zstackwoodpecker.zstack_test.checker_factory as checker_factory
        checker = checker_factory.CheckerFactory().create_checker(self)
        checker.check()
        super(ZstackTestVm, self).check()

    def set_creation_option(self, vm_creation_option):
        self.vm_creation_option = vm_creation_option

    def get_creation_option(self):
        return self.vm_creation_option

    def update(self):
        '''
        If vm's status was changed by none vm operations, it needs to call
        vm.update() to update vm's infromation. 

        The none vm operations: host.maintain() host.delete(), zone.delete()
        cluster.delete()
        '''
        super(ZstackTestVm, self).update()
        if self.get_state != vm_header.EXPUNGED:
            updated_vm = test_lib.lib_get_vm_by_uuid(self.vm.uuid)
            if updated_vm:
                self.vm = updated_vm
                #vm state need to chenage to stopped, if host is deleted
                host = test_lib.lib_find_host_by_vm(updated_vm)
                if not host and self.vm.state != vm_header.STOPPED:
                    self.set_state(vm_header.STOPPED)
            else:
                self.set_state(vm_header.EXPUNGED)
            return self.vm

    def add_nic(self, l3_uuid):
        '''
        Add a new NIC device to VM. The NIC device will connect with l3_uuid.
        '''
        self.vm = net_ops.attach_l3(l3_uuid, self.get_vm().uuid)
        return self.get_vm()

    def remove_nic(self, nic_uuid):
        '''
        Detach a NIC from VM.
        '''
        self.vm = net_ops.detach_l3(nic_uuid)
        return self.get_vm()

    def set_delete_policy(self, policy):
        test_lib.lib_set_delete_policy(category = 'vm', value = policy)
        super(ZstackTestVm, self).set_delete_policy(policy)

    def set_delete_delay_time(self, delay_time):
        test_lib.lib_set_expunge_time(category = 'vm', value = delay_time)
        super(ZstackTestVm, self).set_delete_delay_time(delay_time)

