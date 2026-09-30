#!/bin/bash
echo "=== models 表结构 ==="
docker exec holaros-mysql mysql -uroot -pholar_mysql_root holar_portal -e "DESCRIBE models" 2>/dev/null
echo
echo "=== models 表前5行 ==="
docker exec holaros-mysql mysql -uroot -pholar_mysql_root holar_portal -e "SELECT * FROM models LIMIT 5" 2>/dev/null
echo
echo "=== 表数量统计 ==="
docker exec holaros-mysql mysql -uroot -pholar_mysql_root holar_portal -N -e "SELECT COUNT(*) FROM models" 2>/dev/null
