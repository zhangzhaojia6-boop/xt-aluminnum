"""
禁用班长(BZ)角色的 virtual_role_qr 设备和账号。

根因：提交 5e66f6c 创建了 12 个班长扫码入口，后续从 OWNER_QR_SPECS 移除了 BZ，
但数据库中的设备和账号仍然存在。seed_virtual_role_qr_accounts() 在启动时会
保持这些账号为 active 状态。

解决：将所有 {车间}-BZ 的设备和对应的 shift_leader 账号设为 inactive。
"""
import psycopg2

DB_URL = 'postgresql://bypass_user:xt_bypass_2026@8.140.218.13:5432/aluminum_bypass'


def main() -> None:
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # 查找所有 BZ 设备
    cur.execute("""
        SELECT e.id, e.code, e.name, e.is_active
        FROM equipment e
        WHERE e.code LIKE '%-BZ' AND e.equipment_type = 'virtual_role_qr'
        ORDER BY e.code
    """)
    bz_equipment = cur.fetchall()

    print(f"找到 {len(bz_equipment)} 个班长设备：")
    active_eq = 0
    for eq_id, code, name, is_active in bz_equipment:
        status = "active" if is_active else "inactive"
        print(f"  - {code}: {name} ({status})")
        if is_active:
            active_eq += 1

    if not bz_equipment:
        print("没有找到需要禁用的班长设备")
        cur.close()
        conn.close()
        return

    # 查找对应的账号
    bz_usernames = [code.upper() for _, code, _, _ in bz_equipment]
    cur.execute("""
        SELECT u.id, u.username, u.name, u.is_active, u.last_login
        FROM users u
        WHERE u.username = ANY(%s) AND u.role = 'shift_leader'
        ORDER BY u.username
    """, (bz_usernames,))
    bz_users = cur.fetchall()

    print(f"\n找到 {len(bz_users)} 个班长账号：")
    active_users = 0
    for user_id, username, name, is_active, last_login in bz_users:
        login_status = "已登录" if last_login else "从未登录"
        status = "active" if is_active else "inactive"
        print(f"  - {username}: {name} ({status}, {login_status})")
        if is_active:
            active_users += 1

    # 确认禁用
    print(f"\n即将禁用：")
    print(f"  - {active_eq} 个 active 设备")
    print(f"  - {active_users} 个 active 账号")

    if active_eq == 0 and active_users == 0:
        print("\n所有班长设备和账号已经是 inactive 状态，无需操作")
        cur.close()
        conn.close()
        return

    confirm = input("\n确认禁用？(yes/no): ").strip().lower()
    if confirm != 'yes':
        print("取消操作")
        cur.close()
        conn.close()
        return

    # 禁用账号
    user_ids = [user_id for user_id, _, _, is_active, _ in bz_users if is_active]
    if user_ids:
        cur.execute("UPDATE users SET is_active = false WHERE id = ANY(%s)", (user_ids,))
        print(f"✓ 已禁用 {len(user_ids)} 个账号")

    # 禁用设备
    eq_ids = [eq_id for eq_id, _, _, is_active in bz_equipment if is_active]
    if eq_ids:
        cur.execute("UPDATE equipment SET is_active = false WHERE id = ANY(%s)", (eq_ids,))
        print(f"✓ 已禁用 {len(eq_ids)} 个设备")

    conn.commit()

    print("\n验证：")

    # 验证结果
    cur.execute("""
        SELECT COUNT(*) FROM equipment
        WHERE code LIKE '%-BZ' AND equipment_type = 'virtual_role_qr' AND is_active = true
    """)
    remaining_eq = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM users
        WHERE username = ANY(%s) AND role = 'shift_leader' AND is_active = true
    """, (bz_usernames,))
    remaining_users = cur.fetchone()[0]

    if remaining_eq == 0 and remaining_users == 0:
        print("  ✓ 所有班长设备和账号已设为 inactive")
    else:
        print(f"  ⚠ 仍有 {remaining_eq} 个 active 设备和 {remaining_users} 个 active 账号")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
