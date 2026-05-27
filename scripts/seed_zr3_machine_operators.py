"""
为 ZR3 车间的 9 台机器创建主操账号和二维码设备。

根因：2026-05-27 禁用了主操账号的自动创建（防止已删除账号复活），
但 ZR3 的主操账号可能从未创建过，导致扫码无法登录。
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.auth import get_password_hash
from app.models.master import Equipment, Workshop
from app.models.system import User
from app.services.equipment_service import generate_random_pin


def main() -> None:
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

    with Session(engine) as db:
        # 查找 ZR3 车间
        workshop = db.execute(select(Workshop).where(Workshop.code == 'ZR3')).scalar_one_or_none()
        if not workshop:
            print("错误：未找到 ZR3 车间")
            return

        print(f"车间: {workshop.code} - {workshop.name} (ID: {workshop.id})")

        # 查找 ZR3 的所有机器
        equipment_list = db.execute(
            select(Equipment)
            .where(Equipment.workshop_id == workshop.id)
            .where(Equipment.equipment_type == 'cast_roller')
            .order_by(Equipment.code)
        ).scalars().all()

        print(f"\n找到 {len(equipment_list)} 台机器")

        created = 0
        updated = 0

        for equipment in equipment_list:
            username = equipment.code
            user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()

            if user is None:
                # 创建新账号
                pin = generate_random_pin(6)
                user = User(
                    username=username,
                    password_hash=get_password_hash(pin),
                    name=f"{workshop.name} {equipment.name}",
                    role='machine_operator',
                    workshop_id=workshop.id,
                    team_id=None,
                    data_scope_type='self_workshop',
                    assigned_shift_ids=equipment.assigned_shift_ids or [1, 2, 3],
                    is_mobile_user=True,
                    is_reviewer=False,
                    is_manager=False,
                    is_active=(equipment.operational_status == 'running'),
                    pin_code=pin,
                )
                db.add(user)
                db.flush()

                equipment.bound_user_id = user.id
                print(f"  ✓ 创建 {username} - {user.name} (PIN: {pin})")
                created += 1
            else:
                # 更新现有账号
                user.name = f"{workshop.name} {equipment.name}"
                user.role = 'machine_operator'
                user.workshop_id = workshop.id
                user.is_active = (equipment.operational_status == 'running')
                equipment.bound_user_id = user.id
                print(f"  ✓ 更新 {username} - {user.name}")
                updated += 1

        db.commit()

        print(f"\n完成：创建 {created} 个账号，更新 {updated} 个账号")


if __name__ == '__main__':
    main()
