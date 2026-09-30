#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 K8s PrometheusRule CRD (JSON) 转成 plant01 Prometheus 能直接加载的原生规则文件。

要点:
  1. 收集每个 PrometheusRule 的 spec.groups
  2. 组名冲突自动去重(加 PrometheusRule 名前缀)
  3. 规则名冲突去重(保留首个定义, 记录来源)
  4. 输出 {'groups': [...]} 结构
  5. 统计 alert / record 数量
用法: convert_rules.py <cluster-rules-all.json> <out.yaml>
"""
import json
import sys
from collections import defaultdict

# PyYAML 5.4 的 SafeDumper 不认识 OrderedDict, 直接用普通 dict
# (Python 3.7+ dict 保序, 且 PyYAML 只 hook 了 dict 的 representer)
OrderedDict = dict


def main():
    src, dst = sys.argv[1], sys.argv[2]
    doc = json.load(open(src, encoding='utf-8'), object_pairs_hook=OrderedDict)
    items = doc.get('items', [])

    used_group_names = set()
    out_groups = OrderedDict()          # gname -> group dict (去重后的规则集合)
    dup_rules = defaultdict(list)       # rule_name -> [来源 PR]  (仅完全相同的定义)
    n_alert = n_record = 0
    src_map = defaultdict(set)          # gname -> {来源 PR}
    placed = defaultdict(set)           # (gname, canon) -> 已放入, 避免逐字重复

    for it in sorted(items, key=lambda x: x['metadata']['name']):
        pr_name = it['metadata']['name']
        for g in it['spec'].get('groups', []) or []:
            gname = g.get('name', 'unnamed')

            # ---- 组名冲突: 重命名 ----
            base = gname
            if gname in used_group_names:
                gname = '%s__%s' % (pr_name, base)
            k = 2
            while gname in used_group_names:
                gname = '%s__%s_%d' % (pr_name, base, k)
                k += 1
            used_group_names.add(gname)
            src_map[gname].add(pr_name)

            entry = out_groups.setdefault(
                gname, OrderedDict([('name', gname), ('rules', [])])
            )
            if 'interval' in g:
                entry['interval'] = g['interval']
            if 'limit' in g:
                entry['limit'] = g['limit']

            for r in g.get('rules', []) or []:
                rname = r.get('alert') or r.get('record')
                # ⚠️ 关键: 按【完整定义】去重, 不是按规则名去重!
                #    kube-prometheus-stack 里同名规则常有多个合法变体:
                #      KubeAPIErrorBudgetBurn 有 4 个(warning/critical × 不同时间窗)
                #      KubeletClientCertificateExpiration warning + critical
                #      cluster_quantile:*:histogram_quantile 有 0.5/0.9/0.99
                #    按名去重会丢掉一半语义(已实测: 230 → 188)。
                canon = json.dumps(r, sort_keys=True, ensure_ascii=False)
                if canon in placed[gname]:
                    dup_rules[rname].append(pr_name)
                    continue
                placed[gname].add(canon)
                entry['rules'].append(OrderedDict(r))
                if 'alert' in r:
                    n_alert += 1
                elif 'record' in r:
                    n_record += 1

    # ---- 写文件 ----
    with open(dst, 'w', encoding='utf-8') as f:
        f.write('---\n')
        f.write('# ============================================================\n')
        f.write('#  K8s 集群告警/记录规则 —— 从集群 PrometheusRule CRD 同步而来\n')
        f.write('#\n')
        f.write('#  来源: 集群 10.100.10.10  monitoring namespace\n')
        f.write('#        共 %d 个 PrometheusRule\n' % len(items))
        f.write('#  规则: alert=%d  record=%d  合计=%d\n'
                % (n_alert, n_record, n_alert + n_record))
        f.write('#\n')
        f.write('#  ⚠️ 本文件由脚本自动生成,请勿手工编辑;\n')
        f.write('#     集群侧规则变更后重新导出覆盖即可。\n')
        f.write('#  ⚠️ 依赖集群指标: 需集群 Prometheus remote_write 到本机 :9091,\n')
        f.write('#     否则这些规则会因无数据而不触发(health 会显示 err/no-data)。\n')
        f.write('# ============================================================\n')
        import yaml
        yaml.safe_dump(
            {'groups': list(out_groups.values())},
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=100000,
        )

    # ---- 统计输出 ----
    print('  输入 PrometheusRule : %d 个' % len(items))
    print('  输出 group          : %d 个' % len(out_groups))
    print('  输出规则            : alert=%d  record=%d  合计=%d'
          % (n_alert, n_record, n_alert + n_record))
    if dup_rules:
        print('  ℹ️ 逐字完全重复的规则 %d 个(已去重, 不影响语义):'
              % len(dup_rules))
        for k in sorted(dup_rules):
            print('      %s' % k)


if __name__ == '__main__':
    main()
