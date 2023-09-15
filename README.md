# ansible tools

# only tested on centos8.5.2111 

1. 挑选测试集群任意一节点作为ansible执行节点，执行 prepare.sh

2. 服务器配置免密登陆
   1. 修改 config.ini 文件，主要添加需要配置免密的节点ip，以及登陆的用户名和密码
   2. 执行 ansible-playhook password-less-ssh.yml
   
3. iperf 压测
   1. 修改
   2. 执行
   
4. fio-plot压测
   1. 修改
   2. 执行
