from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类
from datetime import datetime
from .database import PurchaseDB

@register(
    name="SpendFlow",
    description="物品购买记录统计插件",
    version="1.1",
    author="sheetung"
)
class SpendFlowPlugin(BasePlugin):
    def __init__(self, host: APIHost):
        self.ap = host.ap
        self.db = PurchaseDB()  # 初始化数据库连接

    @handler(GroupMessageReceived)
    async def on_message(self, ctx: EventContext):
        msg = str(ctx.event.message_chain).strip().lstrip('/')
        # launcher_id = str(ctx.event.launcher_id)
        # launcher_type = str(ctx.event.launcher_type)
        
        if not self.check_access_control(ctx):
            self.ap.logger.info(f'根据访问控制，插件[KeysChat]忽略消息\n')
            return

        if not msg.startswith("jw"):
            return
        args = msg.split()[1:]  # 去除命令头
        user_id = str(ctx.event.sender_id)

        if not args:
            await ctx.reply("🛒 消费记录插件\n"
                        "格式：jw [物品] [平台] [价格] <日期>\n"
                        "示例：jw 显卡 京东 2999 2024-04-27\n"
                        "其他命令：\n"
                        "jw v → 查看统计\n"
                        "jw d 序号 → 删除记录")
            return

        # 命令路由
        try:
            if args[0] == 'v':
                await self._show_stats(ctx, user_id)
            elif args[0] == 'd' and len(args) > 1:
                await self._delete_purchase(ctx, args[1])
            else:
                await self._add_purchase(ctx, user_id, args)
        except Exception as e:
            await ctx.reply(f"⚠️ 命令执行出错: {str(e)}")

    async def _add_purchase(self, ctx, user_id, args):
        """处理添加命令"""
        try:
            if len(args) >= 4:  # 当参数包含日期时
                date_str = args[-1]
                # 尝试常见日期格式
                formats = [
                    "%Y-%m-%d",   # 2024-04-27
                    "%Y/%m/%d",   # 2024/04/27
                    "%Y%m%d",     # 20240427
                    "%d/%m/%Y",   # 27/04/2024
                    "%m/%d/%Y"    # 04/27/2024
                ]
                
                parsed_date = None
                for fmt in formats:
                    try:
                        parsed_date = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if not parsed_date:
                    await ctx.reply("❌ 日期格式错误，请使用类似 2024-04-27 的格式")
                    return
                    
                if parsed_date > datetime.now():
                    await ctx.reply("❌ 消费日期不能晚于今天")
                    return
                    
                date = parsed_date.strftime("%Y-%m-%d")
                args = args[:-1]
            # 参数完整性检查
            if len(args) < 3:
                await ctx.reply("❌ 参数不足\n格式：jw [物品] [平台] [价格] <日期>")
                return
            price = float(args[-1])
            platform = args[-2]
            item = " ".join(args[:-2])
            pid = self.db.add_purchase(user_id, item, platform, price, date)
            
            # 生成详情报告
            detail_msg = [
                f"✅ 已记录 #{pid}",
                f"▫️物品：{item}",
                f"▫️平台：{platform}",
                f"▫️金额：{price:.2f}元",
                f"▫️日期：{date or '今日'}"
            ]
            await ctx.reply("\n".join(detail_msg))
        except ValueError:
            await ctx.reply("❌ 价格必须为数字")
        except Exception as e:
            await ctx.reply(f"❌ 添加失败: {str(e)}")
            
    async def _show_stats(self, ctx, user_id):
        """显示统计信息"""
        records = self.db.get_purchases(user_id)
        if not records:
            await ctx.reply("📭 暂无消费记录")
            return
        total = 0.0
        report = ["📊 消费统计"]
        for idx, r in enumerate(records, 1):  # 从 1 开始编号
            days = (datetime.now() - datetime.strptime(r[4], "%Y-%m-%d")).days + 1
            daily_cost = r[3] / days
            total += daily_cost
            report.append(
                f"#{idx} {r[1]} | {r[3]}元\n"  # 显示虚拟序号
                f"平台：{r[2]} | 日均：{daily_cost:.2f}元/天"
            )
        report.append(f"---\n总计日均：{total:.2f}元/天")
        await ctx.reply("\n".join(report))

    async def _delete_purchase(self, ctx, virtual_id):
        """通过虚拟序号删除并显示详情"""
        try:
            user_id = str(ctx.event.sender_id)
            records = self.db.get_purchases(user_id)
            
            # 验证序号有效性
            if not 1 <= int(virtual_id) <= len(records):
                await ctx.reply("❌ 无效序号")
                return
                
            # 获取目标记录
            target_record = records[int(virtual_id)-1]
            real_id = target_record[0]
            item = target_record[1]
            platform = target_record[2]
            price = target_record[3]
            date = target_record[4]
            
            # 执行删除
            if self.db.delete_purchase(real_id):
                # 构建详情消息
                detail_msg = [
                    f"✅ 已删除记录 #{virtual_id}",
                    "▫️物品：{}".format(item),
                    "▫️平台：{}".format(platform),
                    "▫️金额：{:.2f}元".format(price),
                    "▫️日期：{}".format(date)
                ]
                await ctx.reply("\n".join(detail_msg))
            else:
                await ctx.reply("❌ 删除失败")
        except ValueError:
            await ctx.reply("❌ 请输入数字序号")
        except Exception as e:
            await ctx.reply(f"⚠️ 错误: {str(e)}")

    def check_access_control(self, ctx: EventContext) -> bool:
        """
        访问控制检查函数
        :param pipeline_cfg: 流水线配置对象
        :param launcher_type: 请求类型 'group' 或 'person'
        :param launcher_id: 请求来源ID
        :return: 是否允许通过访问控制
        """
        launcher_id = str(ctx.event.launcher_id)
        launcher_type = str(ctx.event.launcher_type)
        mode = ctx.event.query.pipeline_config['trigger']['access-control']['mode']
        sess_list = ctx.event.query.pipeline_config['trigger']['access-control'][mode]

        # 处理通配符匹配
        wildcard = f"{launcher_type}_*"
        if wildcard in sess_list:
            return mode == 'whitelist'  # 白名单模式遇到通配符直接放行
        # 构建完整会话标识
        current_session = f"{launcher_type}_{launcher_id}"
        
        # 判断匹配结果
        in_list = current_session in sess_list
        return in_list if mode == 'whitelist' else not in_list

    # 插件卸载时触发
    def __del__(self):
        pass