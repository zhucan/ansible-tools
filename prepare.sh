#! /bin/bash

# update repo
cd /etc/yum.repos.d/
sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-*
sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-*

# install
wget https://rpmfind.net/linux/centos/8-stream/AppStream/x86_64/os/Packages/sshpass-1.09-4.el8.x86_64.rpm
rpm -Uvh sshpass-1.09-4.el8.x86_64.rpm --force
rm -f sshpass-1.09-4.el8.x86_64.rpm
dnf install epel-release -y
dnf install python3 python3-pip -y
dnf install rsync -y 
pip3 install --upgrade pip -i  https://pypi.tuna.tsinghua.edu.cn/simple/
pip3 install setuptools_rust -i https://pypi.tuna.tsinghua.edu.cn/simple/
pip3 install ansible-core==2.11.12 -i https://pypi.tuna.tsinghua.edu.cn/simple/
pip3 install ansible -i https://pypi.tuna.tsinghua.edu.cn/simple/
