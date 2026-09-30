#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全校验: 确认被去重的规则是"逐字相同"的, 而不是定义不同被误吞。"""
import json
import sys

d = json.load(open(sys.argv[1], encoding='utf-8'))

# 收集所有规则实例, 按 (类型, 名字) 分组
buckets = {}
for it in d['items']:
    pr = it['metadata']['name']
    for g in it['spec'].get('groups', []) or []:
        for r in g.get('rules', []) or []:
            name = r.get('alert') or r.get('record')
            key = ('alert' if 'alert' in r else 'record', name)
            buckets.setdefault(key, []).append((pr, g['name'], r))

dups = {k: v for k, v in buckets.items() if len(v) > 1}

print('规则实例总数 =', sum(len(v) for v in buckets.values()))
print('唯一规则名数 =', len(buckets))
print('出现多次的名字数 =', len(dups))
print()

def canon(r):
    # 逐字比较: 类型/表达式/for/keep_firing_for/labels/annotations
    return json.dumps(r, sort_keys=True, ensure_ascii=False)

bad = 0
for (kind, name), lst in sorted(dups.items()):
    sigs = {}
    for pr, gname, r in lst:
        sigs.setdefault(canon(r), []).append('%s/%s' % (pr, gname))
    if len(sigs) == 1:
        print('  ✅ 逐字相同 (%d 份): %-12s %s' % (len(lst), kind, name))
    else:
        bad += 1
        print('  ❌ 定义不同!   %-12s %s' % (kind, name))
        for i, (sig, srcs) in enumerate(sigs.items(), 1):
            rr = json.loads(sig)
            print('       变体%d (%d 份) 来源: %s' % (i, len(srcs), ', '.join(srcs)))
            print('         expr = %s' % (rr.get('expr', '')[:200].replace('\n', ' ')))
            print('         for  = %s   labels=%s' % (rr.get('for'), rr.get('labels')))

print()
print('结论: 出现多次且定义不同的规则名数量 =', bad)
if bad:
    print('  ⚠️ 这些规则若被去重, 会丢掉部分语义! 需要改为"按定义去重"或改名共存。')
else:
    print('  ✅ 所有重复项都是逐字副本, 去重是安全的。')
