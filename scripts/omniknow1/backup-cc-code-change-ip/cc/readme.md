# 自动化脚本



**请将当前目录放到根目录'/'下**



## 常用命令

**service文件存放于/etc/systemd/system**

```
# 激活服务(执行一遍就行) 
sudo systemctl enable xx.service  
# 启动服务 
sudo systemctl start xx.service
# 停用服务  
sudo systemctl stop  xx.service
# 查看服务状态 
sudo systemctl status xx.service
# 删除服务(先stop服务) 
sudo rm /etc/systemd/system/xx.service
```

## 验证脚本是否可用

**因为涉及多个服务以及需要服务器开/关机试验比较繁琐，可以先拿一个服务做手动验证。**

**例如：启动聊天大模型服务作为例子。**

```
#复制service到系统目录下
cp /cc/bash/chat_doc_llm2.service /etc/systemd/system/
#修改服务权限
sudo chmod +x /etc/systemd/system/chat_doc_llm2.service
#激活服务
sudo systemctl enable chat_doc_llm2.service
#手动启动服务
sudo systemctl start chat_doc_llm2.service


#验证服务是否启动（2选1）
1) sudo systemctl status chat_doc_llm2.service  如果是running，表示服务已经其他，失败会有日志提示
2) netstat -tunlp | grep 端口号 如果端口被占用，说明服务已经启动。
```

**重复上述几个服务，如果服务手动启动没问题，关机后再开机，等待系统启动完成后，通过上述命令再次验证各个服务启动情况。**

## 自动化批量脚本

> **请先将cc下面的bash和service目录放到系统根目录下，如放在其他目录，请将脚本路径进行修改。**

```
cp /cc/service/* /etc/systemd/system/

sudo chmod +x /etc/systemd/system/chat_doc_api.service

sudo chmod +x /etc/systemd/system/chat_doc_llm2.service

sudo chmod +x /etc/systemd/system/chat_doc_speech.service

sudo chmod +x  /etc/systemd/system/chat_doc_web.service

sudo systemctl enable chat_doc_api.service

sudo systemctl enable chat_doc_llm2.service

sudo systemctl enable chat_doc_speech.service

sudo systemctl enable chat_doc_web.service
```
