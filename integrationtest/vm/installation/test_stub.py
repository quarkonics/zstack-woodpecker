import os
import subprocess
import time

import zstacklib.utils.ssh as ssh
import zstackwoodpecker.test_util as test_util
import zstackwoodpecker.test_lib as test_lib
import zstackwoodpecker.operations.resource_operations as res_ops
import zstackwoodpecker.zstack_test.zstack_test_vm as zstack_vm_header

def create_vlan_vm(image_name, l3_name=None, disk_offering_uuids=None):
    image_uuid = test_lib.lib_get_image_by_name(image_name).uuid
    if not l3_name:
        l3_name = os.environ.get('l3VlanNetworkName1')

    l3_net_uuid = test_lib.lib_get_l3_by_name(l3_name).uuid
    return create_vm([l3_net_uuid], image_uuid, 'zs_install_%s' % image_name, \
            disk_offering_uuids)

def create_vm(l3_uuid_list, image_uuid, vm_name = None, \
        disk_offering_uuids = None, default_l3_uuid = None):
    vm_creation_option = test_util.VmOption()
    conditions = res_ops.gen_query_conditions('type', '=', 'UserVm')
    instance_offering_uuid = res_ops.query_resource(res_ops.INSTANCE_OFFERING, conditions)[0].uuid
    vm_creation_option.set_instance_offering_uuid(instance_offering_uuid)
    vm_creation_option.set_l3_uuids(l3_uuid_list)
    vm_creation_option.set_image_uuid(image_uuid)
    vm_creation_option.set_name(vm_name)
    vm_creation_option.set_data_disk_uuids(disk_offering_uuids)
    vm_creation_option.set_default_l3_uuid(default_l3_uuid)
    vm = zstack_vm_header.ZstackTestVm()
    vm.set_creation_option(vm_creation_option)
    vm.create()
    return vm

def check_str(string):
    if string == None:
        return ""
    return string

def execute_shell_in_process(cmd, tmp_file, timeout = 1200, no_timeout_excep = False):
    logfd = open(tmp_file, 'w', 0)
    process = subprocess.Popen(cmd, executable='/bin/sh', shell=True, stdout=logfd, stderr=logfd, universal_newlines=True)

    start_time = time.time()
    while process.poll() is None:
        curr_time = time.time()
        test_time = curr_time - start_time
        if test_time > timeout:
            process.kill()
            logfd.close()
            logfd = open(tmp_file, 'r')
            test_util.test_logger('[shell:] %s [timeout logs:] %s' % (cmd, '\n'.join(logfd.readlines())))
            logfd.close()
            if no_timeout_excep:
                test_util.test_logger('[shell:] %s timeout, after %d seconds' % (cmd, test_time))
                return 1
            else:
                os.system('rm -f %s' % tmp_file)
                test_util.test_fail('[shell:] %s timeout, after %d seconds' % (cmd, timeout))
        if test_time%10 == 0:
            print('shell script used: %ds' % int(test_time))
        time.sleep(1)
    logfd.close()
    logfd = open(tmp_file, 'r')
    test_util.test_logger('[shell:] %s [logs]: %s' % (cmd, '\n'.join(logfd.readlines())))
    logfd.close()
    return process.returncode

def copy_id_dsa(vm_inv, ssh_cmd, tmp_file):
    src_file = '/root/.ssh/id_dsa'
    target_file = '/root/.ssh/id_dsa'
    if not os.path.exists(src_file):
        os.system("ssh-keygen -t dsa -N '' -f %s" % src_file)
    test_lib.lib_scp_file_to_vm(vm_inv, src_file, target_file)
    cmd = '%s "chmod 600 /root/.ssh/id_dsa"' % ssh_cmd
    process_result = execute_shell_in_process(cmd, tmp_file)

def copy_id_rsa(vm_inv, ssh_cmd, tmp_file):
    src_file = '/root/.ssh/id_rsa'
    target_file = '/root/.ssh/id_rsa'
    if not os.path.exists(src_file):
        os.system("ssh-keygen -t rsa -N '' -f %s" % src_file)
    test_lib.lib_scp_file_to_vm(vm_inv, src_file, target_file)
    cmd = '%s "chmod 600 /root/.ssh/id_rsa"' % ssh_cmd
    process_result = execute_shell_in_process(cmd, tmp_file)

def copy_id_dsa_pub(vm_inv):
    src_file = '/root/.ssh/id_dsa.pub'
    target_file = '/root/.ssh/authorized_keys'
    if not os.path.exists(src_file):
        os.system("ssh-keygen -t dsa -N '' -f %s" % src_file)
    test_lib.lib_scp_file_to_vm(vm_inv, src_file, target_file)

def prepare_test_env(vm_inv, aio_target):
    zstack_install_script = os.environ['zstackInstallScript']
    target_file = '/root/zstack_installer.sh'
    test_lib.lib_scp_file_to_vm(vm_inv, zstack_install_script, target_file)

    all_in_one_pkg = os.environ['zstackPkg']
    test_lib.lib_scp_file_to_vm(vm_inv, all_in_one_pkg, aio_target)

    vm_ip = vm_inv.vmNics[0].ip
    ssh.make_ssh_no_password(vm_ip, test_lib.lib_get_vm_username(vm_inv), \
            test_lib.lib_get_vm_password(vm_inv))

def upgrade_zstack(ssh_cmd, target_file, tmp_file):
    env_var = "WEBSITE='%s'" % 'localhost'

    cmd = '%s "%s bash /root/zstack_installer.sh -u -f %s"' \
            % (ssh_cmd, env_var, target_file)

    process_result = execute_shell_in_process(cmd, tmp_file)

    if process_result != 0:
        cmd = '%s "cat /tmp/zstack_installation.log"' % ssh_cmd
        execute_shell_in_process(cmd, tmp_file)
        if 'no management-node-ready message received within' in open(tmp_file).read():
            times = 30
            cmd = '%s "zstack-ctl status"' % ssh_cmd
            while (times > 0):
                time.sleep(10)
                process_result = execute_shell_in_process(cmd, tmp_file, 10, True)
                times -= 0
                if process_result == 0:
                    test_util.test_logger("management node start after extra %d seconds" % (30 - times + 1) * 10 )
                    return 0
                test_util.test_logger("mn node is still not started up, wait for another 10 seconds...")
            else:
                test_util.test_fail('zstack upgrade failed')

def execute_all_install(ssh_cmd, target_file, tmp_file):
    env_var = "ZSTACK_ALL_IN_ONE='%s' WEBSITE='%s'" % \
            (target_file, 'localhost')

    cmd = '%s "%s bash /root/zstack_installer.sh -d -a"' % (ssh_cmd, env_var)

    process_result = execute_shell_in_process(cmd, tmp_file)

    if process_result != 0:
        cmd = '%s "cat /tmp/zstack_installation.log"' % ssh_cmd
        execute_shell_in_process(cmd, tmp_file)
        if 'no management-node-ready message received within' in open(tmp_file).read():
            times = 30
            cmd = '%s "zstack-ctl status"' % ssh_cmd
            while (times > 0):
                time.sleep(10)
                process_result = execute_shell_in_process(cmd, tmp_file, 10, True)
                times -= 0
                if process_result == 0:
                    test_util.test_logger("management node start after extra %d seconds" % (30 - times + 1) * 10 )
                    return 0
                test_util.test_logger("mn node is still not started up, wait for another 10 seconds...")
            else:
                test_util.test_fail('zstack installation failed')

def only_install_zstack(ssh_cmd, target_file, tmp_file):
    env_var = "WEBSITE='%s'" % 'localhost'

    cmd = '%s "%s bash /root/zstack_installer.sh -d -i -f %s"' % (ssh_cmd, env_var, target_file)

    process_result = execute_shell_in_process(cmd, tmp_file)

    if process_result != 0:
        cmd = '%s "cat /tmp/zstack_installation.log"' % ssh_cmd
        execute_shell_in_process(cmd, tmp_file)
        test_util.test_fail('zstack installation failed')

def check_installation(ssh_cmd, tmp_file):
    cmd = '%s "/usr/bin/zstack-cli LogInByAccount accountName=admin password=password"' % ssh_cmd
    process_result = execute_shell_in_process(cmd, tmp_file)
    if process_result != 0:
        test_util.test_fail('zstack-cli login failed')

    cmd = '%s "/usr/bin/zstack-cli CreateZone name=zone1 description=zone1"' % ssh_cmd
    process_result = execute_shell_in_process(cmd, tmp_file)
    if process_result != 0:
        test_util.test_fail('zstack-cli create zone failed')

    cmd = '%s "/usr/bin/zstack-cli QueryZone name=zone1 description=zone1"' % ssh_cmd
    process_result = execute_shell_in_process(cmd, tmp_file)
    if process_result != 0:
        test_util.test_fail('zstack-cli Query zone failed')
