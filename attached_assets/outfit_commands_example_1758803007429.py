
"""
مثال شامل لأوامر الملابس في Highrise Bot
أوامر /لبس و /خلع مع الشرح التفصيلي

هذا الملف يحتوي على:
1. أمر /لبس - لتطبيق الملابس على البوت
2. أمر /خلع - لإزالة قطعة ملابس من البوت
3. دوال مساعدة للتحقق من صحة أكواد الملابس
4. نظام دمج الملابس مع الزي الحالي
"""

import re
from highrise import BaseBot, Item
from typing import Dict, List, Optional

class OutfitManager:
    """مدير الملابس - يحتوي على جميع دوال إدارة الملابس"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        
    def is_valid_clothing_code(self, item_id: str) -> bool:
        """فحص صحة كود الملابس"""
        try:
            # فحص أن الكود ليس فارغ
            if not item_id or len(item_id.strip()) == 0:
                return False

            # فحص وجود علامة - في الكود
            if '-' not in item_id:
                return False

            # فحص أن الكود لا يحتوي على أحرف غير مقبولة
            invalid_chars = [' ', '\n', '\t', '\r']
            if any(char in item_id for char in invalid_chars):
                return False

            # قائمة بأنواع الملابس المعروفة
            valid_prefixes = [
                'hair_front', 'hair_back', 'hat', 'mask', 'shirt', 'pants', 'shoes',
                'bag', 'handbag', 'watch', 'eye', 'mouth', 'body', 'face_accessory',
                'necklace', 'jacket', 'dress', 'skirt', 'top', 'bottom', 'gloves',
                'eyebrow', 'nose', 'freckle', 'glasses', 'face_hair'
            ]

            # فحص أن الكود يبدأ بنوع ملابس صحيح
            item_type = item_id.split('-')[0]
            if item_type in valid_prefixes:
                return True

            # فحص أنماط أخرى شائعة
            if item_id.startswith(('outfit-', 'clothing-', 'accessory-')):
                return True

            return False

        except Exception as e:
            print(f"خطأ في فحص كود الملابس {item_id}: {e}")
            return False

    def extract_item_id_from_text(self, text: str) -> Optional[str]:
        """استخراج معرف القطعة من النص أو الرابط"""
        try:
            print(f"🔍 بدء استخراج معرف القطعة من النص: {text}")

            # البحث عن النص بين القوسين أولاً
            bracket_match = re.search(r'\[([^\]]+)\]', text)
            if bracket_match:
                bracket_content = bracket_match.group(1).strip()
                print(f"🔍 تم العثور على نص بين القوسين: {bracket_content}")

                # فحص إذا كان الرابط يحتوي على معرف القطعة
                if 'high.rs/item?id=' in bracket_content:
                    # استخراج معرف القطعة من الرابط
                    id_match = re.search(r'id=([^&\s]+)', bracket_content)
                    if id_match:
                        item_id = id_match.group(1)
                        print(f"✅ تم استخراج معرف القطعة من الرابط: {item_id}")
                        return item_id

                # البحث عن أنماط معرفات الملابس في النص
                id_patterns = [
                    r'([a-zA-Z_]+\-[a-zA-Z0-9_]+)',  # نمط الملابس العادي
                    r'id=([^&\s]+)',                 # معرف من الرابط
                    r'item\?id=([^&\s]+)'           # معرف من رابط مباشر
                ]

                for pattern in id_patterns:
                    match = re.search(pattern, bracket_content)
                    if match:
                        potential_id = match.group(1)
                        print(f"🔍 تم العثور على معرف محتمل: {potential_id}")
                        if self.is_valid_clothing_code(potential_id):
                            print(f"✅ تم التعرف على معرف قطعة صالح: {potential_id}")
                            return potential_id

            # إذا لم نجد نص بين القوسين، ابحث عن رابط في النص كاملاً
            url_match = re.search(r'high\.rs/item\?id=([^&\s]+)', text)
            if url_match:
                item_id = url_match.group(1)
                print(f"✅ تم استخراج معرف القطعة من الرابط المباشر: {item_id}")
                return item_id

            print(f"❌ لم يتم العثور على معرف قطعة صالح في النص")
            return None

        except Exception as e:
            print(f"❌ خطأ في استخراج معرف القطعة: {e}")
            return None

    def get_item_category(self, item_id: str) -> str:
        """تحديد فئة قطعة الملابس لتجنب التداخل"""
        try:
            # استخراج النوع الأساسي من الكود
            if '-' in item_id:
                prefix = item_id.split('-')[0]
            else:
                prefix = item_id

            # تصنيف القطع حسب الجزء الذي تغطيه
            categories = {
                'body': 'body',
                'hair_front': 'hair_front',
                'hair_back': 'hair_back',
                'eye': 'face_eyes',
                'eyebrow': 'face_eyebrow',
                'nose': 'face_nose',
                'mouth': 'face_mouth',
                'freckle': 'face_freckle',
                'face_hair': 'face_hair',
                'shirt': 'torso_shirt',
                'jacket': 'torso_jacket',
                'dress': 'torso_dress',
                'top': 'torso_top',
                'pants': 'legs_pants',
                'skirt': 'legs_skirt',
                'shorts': 'legs_shorts',
                'shoes': 'feet_shoes',
                'hat': 'head_hat',
                'glasses': 'head_glasses',
                'mask': 'head_mask',
                'watch': 'arms_watch',
                'bag': 'back_bag',
                'handbag': 'hand_bag',
                'necklace': 'neck_necklace',
                'gloves': 'hands_gloves'
            }

            # إرجاع الفئة أو الكود الأصلي إذا لم نجد تطابق
            return categories.get(prefix, f'other_{prefix}')

        except Exception as e:
            print(f"خطأ في تصنيف القطعة {item_id}: {e}")
            return f'unknown_{item_id}'

    async def wear_outfit_command(self, user, message_content: str) -> str:
        """
        أمر /لبس - دمج الملابس الجديدة مع الزي الحالي
        
        الاستخدام:
        - /لبس hair_front-n_malenew19 shirt-n_basicteenew
        - /لبس [https://high.rs/item?id=hat-n_example]
        - /لبس كود1 كود2 كود3
        """
        try:
            # استخراج أكواد الملابس من الرسالة
            codes_text = message_content[5:].strip()  # إزالة "/لبس "

            if not codes_text:
                return "❌ يرجى تحديد أكواد الملابس\n📝 مثال: /لبس hair_front-n_malenew19 shirt-n_basicteenew\n🔗 أو: /لبس [https://high.rs/item?id=hat-n_example]"

            # محاولة استخراج معرف القطعة من النص بين القوسين
            extracted_id = self.extract_item_id_from_text(codes_text)
            if extracted_id:
                codes = [extracted_id]
                print(f"🎯 تم استخراج وتطبيق معرف القطعة: {extracted_id}")
            else:
                # تقسيم الأكواد التقليدي (دعم المسافات والفواصل)
                codes = [code.strip() for code in re.split(r'[,\s\n]+', codes_text) if code.strip()]

            if not codes:
                return "❌ لم يتم العثور على أكواد صحيحة"

            # الحصول على الزي الحالي للبوت
            current_outfit_items = {}
            try:
                current_outfit = await self.bot.highrise.get_my_outfit()
                if current_outfit and current_outfit.outfit:
                    for item in current_outfit.outfit:
                        # تصنيف القطع حسب النوع
                        item_type = self.get_item_category(item.id)
                        current_outfit_items[item_type] = item
                    print(f"🔍 الزي الحالي: {len(current_outfit.outfit)} قطعة")
                else:
                    print("🔍 لا يوجد زي حالي للبوت")
            except Exception as e:
                print(f"خطأ في الحصول على الزي الحالي: {e}")

            # معالجة الأكواد الجديدة
            new_items = {}
            background_id = None
            invalid_codes = []

            for code in codes:
                # فحص إذا كانت القطعة خلفية
                if code.startswith('bg-'):
                    background_id = code
                    continue

                # فحص صحة الكود
                if not self.is_valid_clothing_code(code):
                    invalid_codes.append(code)
                    print(f"❌ كود غير صحيح: {code}")
                    continue

                try:
                    item = Item(
                        type='clothing',
                        amount=1,
                        id=code,
                        account_bound=False,
                        active_palette=-1
                    )

                    # تصنيف القطعة الجديدة
                    item_type = self.get_item_category(code)
                    new_items[item_type] = item
                    print(f"✅ تم إضافة {item_type}: {code}")

                except Exception as e:
                    print(f"❌ فشل في إنشاء العنصر {code}: {e}")
                    invalid_codes.append(code)

            # دمج الزي الحالي مع القطع الجديدة
            final_outfit = {}

            # إضافة الزي الحالي
            final_outfit.update(current_outfit_items)

            # استبدال القطع الجديدة
            final_outfit.update(new_items)

            # تحويل إلى قائمة
            outfit_items = list(final_outfit.values())

            # إضافة القطع الأساسية المفقودة إذا لزم الأمر
            required_basics = {
                'body': 'body-flesh',
                'face_nose': 'nose-n_01'
            }

            for basic_type, basic_id in required_basics.items():
                if basic_type not in final_outfit:
                    try:
                        basic_item = Item(
                            type='clothing',
                            amount=1,
                            id=basic_id,
                            account_bound=False,
                            active_palette=-1
                        )
                        outfit_items.append(basic_item)
                        print(f"✅ تم إضافة {basic_type} الأساسي: {basic_id}")
                    except Exception as e:
                        print(f"⚠️ فشل في إضافة {basic_type} الأساسي: {e}")

            # تطبيق الزي المدموج
            try:
                await self.bot.highrise.set_outfit(outfit=outfit_items)
                print(f"🎨 تم تطبيق {len(outfit_items)} قطعة ملابس (مدموج)")
            except Exception as outfit_error:
                print(f"❌ فشل في تطبيق الزي: {outfit_error}")
                return f"❌ فشل في تطبيق الزي: {str(outfit_error)}"

            # تطبيق الخلفية إن وجدت
            background_applied = False
            if background_id:
                try:
                    if hasattr(self.bot.highrise, 'set_backdrop'):
                        await self.bot.highrise.set_backdrop(background_id)
                        background_applied = True
                        print(f"🖼️ تم تطبيق الخلفية: {background_id}")
                    else:
                        print(f"❌ دالة الخلفية غير متاحة")
                except Exception as bg_error:
                    print(f"❌ فشل في تطبيق الخلفية {background_id}: {bg_error}")

            # إرسال رسالة في الروم
            room_message = "👔 تم تحديث زي البوت: "
            if new_items:
                room_message += f"{len(new_items)} قطعة جديدة"
            if background_applied:
                room_message += " + خلفية جديدة" if new_items else "خلفية جديدة"

            await self.bot.highrise.chat(room_message)

            # رد خاص للمطور
            response_message = "✅ تقرير التطبيق المدموج:\n"
            response_message += f"👕 الزي النهائي: {len(outfit_items)} قطعة\n"
            if new_items:
                response_message += f"🆕 قطع جديدة: {len(new_items)}\n"
                response_message += f"📝 الأكواد الجديدة: {', '.join([item.id for item in new_items.values()])}\n"
            if len(current_outfit_items) > 0:
                response_message += f"🔄 قطع محفوظة: {len(current_outfit_items)}\n"
            if background_id:
                if background_applied:
                    response_message += f"🖼️ الخلفية: تم تطبيق {background_id}\n"
                else:
                    response_message += f"❌ الخلفية: فشل في تطبيق {background_id}\n"
            if invalid_codes:
                response_message += f"⚠️ أكواد مرفوضة: {', '.join(invalid_codes)}"

            print(f"🎨 تم تطبيق أمر /لبس المدموج للمطور {user.username} - {len(new_items)} جديدة، {len(outfit_items)} إجمالي")
            return response_message

        except Exception as e:
            error_msg = f"❌ خطأ في معالجة أمر /لبس: {str(e)}"
            print(error_msg)
            return error_msg

    async def remove_outfit_item_command(self, user, message_content: str) -> str:
        """
        أمر /خلع - إزالة قطعة ملابس محددة من زي البوت
        
        الاستخدام:
        - /خلع hair_front-n_malenew19
        - /خلع shirt-n_basicteenew
        """
        try:
            # استخراج كود العنصر من الرسالة
            item_code = message_content[5:].strip()  # إزالة "/خلع "

            if not item_code:
                return "❌ يرجى تحديد كود العنصر المراد إزالته.\n📝 مثال: /خلع hair_front-n_malenew19"

            print(f"🔍 محاولة إزالة العنصر: {item_code} للمطور {user.username}")

            # الحصول على الزي الحالي للبوت
            current_outfit_items = []
            try:
                current_outfit = await self.bot.highrise.get_my_outfit()
                if current_outfit and current_outfit.outfit:
                    current_outfit_items = current_outfit.outfit
                    print(f"🔍 الزي الحالي يحتوي على {len(current_outfit_items)} قطعة")
                else:
                    return "❌ لا يوجد زي حالي للبوت"
            except Exception as e:
                print(f"خطأ في الحصول على الزي الحالي: {e}")
                return f"❌ خطأ في الحصول على الزي: {str(e)}"

            # البحث عن العنصر في الزي الحالي
            item_to_remove = None
            for item in current_outfit_items:
                if item.id == item_code:
                    item_to_remove = item
                    break

            if not item_to_remove:
                # عرض قائمة القطع المتاحة للحذف
                available_items = [item.id for item in current_outfit_items]
                items_text = "\n".join([f"• {item}" for item in available_items[:10]])
                if len(available_items) > 10:
                    items_text += f"\n... و {len(available_items) - 10} قطعة أخرى"

                return f"❌ العنصر '{item_code}' غير موجود في الزي الحالي\n\n📋 القطع المتاحة للحذف:\n{items_text}"

            # فحص القطع الأساسية التي لا يجب حذفها
            essential_items = ['body-flesh', 'nose-n_01']
            if item_code in essential_items:
                return f"⚠️ لا يمكن حذف العنصر '{item_code}' لأنه قطعة أساسية"

            # إزالة العنصر من الزي
            updated_outfit = [item for item in current_outfit_items if item.id != item_code]
            print(f"🔄 الزي الجديد سيحتوي على {len(updated_outfit)} قطعة")

            # تطبيق الزي الجديد
            try:
                await self.bot.highrise.set_outfit(outfit=updated_outfit)
                result_message = f"✅ تم إزالة العنصر '{item_code}' من الزي بنجاح\n📊 القطع المتبقية: {len(updated_outfit)}"
                print(f"🗑️ تم إزالة العنصر {item_code} من الزي بنجاح للمطور {user.username}")

                # إرسال رسالة في الروم
                await self.bot.highrise.chat(f"🗑️ تم حذف قطعة من زي البوت")
                return result_message

            except Exception as outfit_error:
                error_details = str(outfit_error)
                print(f"❌ فشل في تطبيق الزي الجديد: {outfit_error}")

                if "not owned" in error_details or "not free" in error_details:
                    return f"❌ لا يمكن تطبيق الزي الجديد - مشكلة في ملكية القطع"
                else:
                    return f"❌ فشل في تطبيق الزي الجديد: {error_details}"

        except Exception as e:
            error_msg = f"❌ خطأ في معالجة أمر /خلع: {str(e)}"
            print(error_msg)
            return error_msg

    async def get_current_outfit_info(self) -> str:
        """عرض تفاصيل الزي الحالي للبوت"""
        try:
            current_outfit = await self.bot.highrise.get_my_outfit()
            if current_outfit and current_outfit.outfit:
                outfit_details = "👔 الزي الحالي للبوت:\n"
                outfit_details += "═" * 30 + "\n"
                for i, item in enumerate(current_outfit.outfit, 1):
                    category = self.get_item_category(item.id)
                    outfit_details += f"{i}. {category}: {item.id}\n"
                outfit_details += f"\n📊 إجمالي القطع: {len(current_outfit.outfit)}"
                return outfit_details
            else:
                return "❌ لا يمكن الحصول على معلومات الزي"
        except Exception as e:
            return f"❌ خطأ في عرض الزي: {str(e)}"


class ExampleBot(BaseBot):
    """مثال لبوت Highrise مع أوامر الملابس"""
    
    def __init__(self):
        super().__init__()
        self.outfit_manager = OutfitManager(self)
        print("🤖 البوت مع إدارة الملابس جاهز!")

    async def on_start(self, session_metadata):
        """عند بدء البوت"""
        print("🚀 البوت بدأ العمل!")
        await self.highrise.chat("👔 بوت إدارة الملابس جاهز! استخدم /لبس أو /خلع")

    async def on_chat(self, user, message: str):
        """معالجة الرسائل"""
        try:
            # فحص صلاحيات المطور (يمكن تخصيص هذا حسب نظامك)
            if not self.is_developer(user.username):
                return

            # أمر /لبس
            if message.startswith("/لبس "):
                result = await self.outfit_manager.wear_outfit_command(user, message)
                await self.highrise.send_whisper(user.id, result)
            
            # أمر /خلع
            elif message.startswith("/خلع "):
                result = await self.outfit_manager.remove_outfit_item_command(user, message)
                await self.highrise.send_whisper(user.id, result)
            
            # أمر /زي (لعرض الزي الحالي)
            elif message == "/زي":
                result = await self.outfit_manager.get_current_outfit_info()
                await self.highrise.send_whisper(user.id, result)

        except Exception as e:
            print(f"خطأ في معالجة الرسالة: {e}")

    def is_developer(self, username: str) -> bool:
        """فحص إذا كان المستخدم مطور - يمكن تخصيص هذا"""
        # ضع هنا أسماء المطورين المخولين
        developers = ["VECTOR000", "اسم_المطور_الآخر"]
        return username in developers

    async def on_whisper(self, user, message: str):
        """معالجة الرسائل الخاصة"""
        try:
            if not self.is_developer(user.username):
                await self.highrise.send_whisper(user.id, "❌ أوامر الملابس متاحة للمطورين فقط")
                return

            # أمر /لبس في الرسائل الخاصة
            if message.startswith("/لبس "):
                result = await self.outfit_manager.wear_outfit_command(user, message)
                await self.highrise.send_whisper(user.id, result)
            
            # أمر /خلع في الرسائل الخاصة
            elif message.startswith("/خلع "):
                result = await self.outfit_manager.remove_outfit_item_command(user, message)
                await self.highrise.send_whisper(user.id, result)
            
            # أمر /زي في الرسائل الخاصة
            elif message == "/زي":
                result = await self.outfit_manager.get_current_outfit_info()
                await self.highrise.send_whisper(user.id, result)
            
            else:
                available_commands = """📋 الأوامر المتاحة:
🔧 /لبس [أكواد] - إضافة ملابس للزي
🗑️ /خلع [كود] - إزالة قطعة من الزي  
👔 /زي - عرض تفاصيل الزي الحالي"""
                await self.highrise.send_whisper(user.id, available_commands)

        except Exception as e:
            print(f"خطأ في معالجة الرسالة الخاصة: {e}")


# مثال للاستخدام في الكود الرئيسي
"""
إذا كنت تريد إضافة هذه الأوامر لبوت موجود، يمكنك:

1. نسخ class OutfitManager إلى ملف منفصل
2. استيراده في البوت الرئيسي
3. إضافة المعالجة في دالة on_chat أو on_whisper

مثال:
from outfit_manager import OutfitManager

class YourBot(BaseBot):
    def __init__(self):
        super().__init__()
        self.outfit_manager = OutfitManager(self)
    
    async def on_whisper(self, user, message):
        if message.startswith("/لبس "):
            result = await self.outfit_manager.wear_outfit_command(user, message)
            await self.highrise.send_whisper(user.id, result)
        elif message.startswith("/خلع "):
            result = await self.outfit_manager.remove_outfit_item_command(user, message)
            await self.highrise.send_whisper(user.id, result)
"""

# ملاحظات مهمة للتنفيذ:
"""
1. تأكد من وجود مكتبة highrise مثبتة
2. ضع أسماء المطورين المخولين في دالة is_developer
3. يمكن تخصيص أنواع الملابس المقبولة في valid_prefixes
4. يمكن إضافة المزيد من أنواع الخلفيات والإكسسوارات
5. النظام يدعم الروابط من high.rs ويستخرج معرفات القطع تلقائياً
6. النظام يحافظ على الزي الحالي ويدمج معه القطع الجديدة
7. يمكن إضافة نظام حفظ واستعادة الأزياء المفضلة
"""
