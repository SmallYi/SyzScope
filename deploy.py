import re
import os

from subprocess import call

syz_config_template="""
{ \
        \"target\": \"linux/amd64\",
        \"http\": \"127.0.0.1:56745\",
        \"workdir\": \"$GOPATH/src/github.com/google/syzkaller/workdir\",
        \"kernel_obj\": \"$KERNEL_PATH\",
        \"image\": \"$IMAGE/stretch.img\",
        \"sshkey\": \"$IMAGE/stretch.id_rsa\",
        \"syzkaller\": \"$GOPATH/src/github.com/google/syzkaller\",
        \"procs\": 8,
        \"type\": \"qemu\",
        \"testcase\": \"$GOPATH/src/github.com/google/syzkaller/workdir/testcase-$HASH\",
        \"vm\": {
                \"count\": 4,
                \"kernel\": \"$KERNEL_PATH/arch/x86/boot/bzImage\",
                \"cpu\": 2,
                \"mem\": 2048
        },
        \"enable_syscalls\" : [
            {}
        ]
}"""

class Deployer:
    def __init__(self):
        self.linux_path = "linux"
        #self.clone_linux()

    def deploy(self, cases):
        for hash in cases:
            case = cases[hash]
            syzkaller_path = self.__run_delopy_script(hash, case)
            self.__write_config(syzkaller_path, case["syz_repro"])
            #self.__write_testcase(case["syz_repro"])

    def clone_linux(self):
        self.__run_linux_clone_script()

    def __run_linux_clone_script(self):
        print("run: scripts/linux-clone.sh {}".format(self.linux_path))
        call(["scripts/linux-clone.sh", self.linux_path], shell=True)

    def __run_delopy_script(self, hash, case):
        commit = case["commit"]
        syzkaller = case["syzkaller"]
        config = case["config"]
        testcase = case["syz_repro"]
        print("run: scripts/deploy.sh {} {} {} {}".format(self.linux_path, hash, commit, syzkaller, config, testcase))
        return call(["scripts/deploy.sh", self.linux_path, hash, commit, syzkaller, config, testcase], shell=True)

    def __write_config(self, syzkaller_path, testcase):
        syscalls = self.__extract_syscalls(testcase)
        if syscalls == []:
            print("No syscalls found in testcase: {}".format(testcase))
            return -1
        last_syscall = syscalls[len(syscalls)-1]
        dependent_syscalls = self.__extract_dependent_syscalls(last_syscall, syzkaller_path)
        syscalls.extend(dependent_syscalls)
        enable_syscalls = "\"" + "\",\n\t\"".join(syscalls)[:-4]
        syz_config_template.format(enable_syscalls)
        print(enable_syscalls)

    def __extract_syscalls(self, testcase):
        res = []
        for line in testcase:
            if line[0] == '#':
                continue
            m = re.search('(\w+(\$\w+)?)\(', line)
            if m == None or len(m.groups()) == 0:
                print("Failed to extract syscall from {}".format(line))
                return -1
            syscall = m.groups()[0]
            res.append(syscall)
        return res

    def __extract_dependent_syscalls(self, last_syscall, syzkaller_path, search_path="sys/linux", extension=".txt"):
        res = []
        dir = os.path.join(syzkaller_path, search_path)
        for file in os.listdir(dir):
            if file.endswith(extension):
                find_it = False
                f = open(os.path.join(dir, file), "r")
                text = f.readlines()
                f.close()
                for line in text:
                    if line.find(last_syscall) != -1:
                        find_it = True
                        break

                if find_it:
                    for line in text:
                        m = re.match('(\w+(\$\w+)?)\(', line)
                        if m == None or len(m.groups()) == 0:
                            print("Failed to extract syscall from {}".format(line))
                            return -1
                        syscall = m.groups()[0]
                        res.append(syscall)
                    break
        return res