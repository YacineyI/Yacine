import sys
import os
import shutil
import time
import random
import asyncio
import json
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from threading import Thread
from werkzeug.utils import secure_filename
from highrise import *
from highrise.models import *
from asyncio import run as arun
from highrise.__main__ import *
from config import Config
import re
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

    async def add_outfit_item_command(self, user, message_content: str) -> str:
        """
        أمر /on - إضافة قطعة ملابس جديدة دون حذف الموجود
        
        الاستخدام:
        - /on hair_front-n_malenew19
        - /on [https://high.rs/item?id=hat-n_example]
        """
        try:
            # استخراج كود الملابس من الرسالة
            codes_text = message_content[3:].strip()  # إزالة "/on "

            if not codes_text:
                return "<#FF6B6B> ❌ Please specify item code\n<#87CEEB> 📝 Example: /on hair_front-n_malenew19\n<#40E0D0> 🔗 Or: /on [https://high.rs/item?id=hat-n_example]"

            # محاولة استخراج معرف القطعة من النص بين القوسين
            extracted_id = self.extract_item_id_from_text(codes_text)
            if extracted_id:
                item_code = extracted_id
                print(f"🎯 تم استخراج وتطبيق معرف القطعة: {extracted_id}")
            else:
                # استخدام الكود مباشرة
                item_code = codes_text.strip()

            # فحص صحة الكود
            if not self.is_valid_clothing_code(item_code):
                return f"<#FF6B6B> ❌ Invalid code: {item_code}\n<#40E0D0> 💡 Check the code or link format"

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

            # إنشاء القطعة الجديدة
            try:
                new_item = Item(
                    type='clothing',
                    amount=1,
                    id=item_code,
                    account_bound=False,
                    active_palette=-1
                )

                # تصنيف القطعة الجديدة
                item_type = self.get_item_category(item_code)
                
                # إضافة القطعة الجديدة للزي الحالي (استبدال إذا كانت من نفس النوع)
                current_outfit_items[item_type] = new_item
                
                print(f"✅ تم إضافة {item_type}: {item_code}")

            except Exception as e:
                print(f"❌ فشل في إنشاء العنصر {item_code}: {e}")
                return f"<#FF6B6B> ❌ Failed to create item: {str(e)}"

            # تحويل إلى قائمة
            outfit_items = list(current_outfit_items.values())

            # إضافة القطع الأساسية المفقودة إذا لزم الأمر
            required_basics = {
                'body': 'body-flesh',
                'face_nose': 'nose-n_01'
            }

            for basic_type, basic_id in required_basics.items():
                if basic_type not in current_outfit_items:
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

            # تطبيق الزي المحدث
            try:
                await self.bot.highrise.set_outfit(outfit=outfit_items)
                print(f"🎨 تم تطبيق {len(outfit_items)} قطعة ملابس")
                
                # إرسال رسالة في الروم
                await self.bot.highrise.chat(f"<#9370DB> 👔 New outfit item added to bot!")
                
                return f"✅ Outfit item added successfully!\n👔 {item_type}: {item_code}\n📊 Total items: {len(outfit_items)}"

            except Exception as outfit_error:
                print(f"❌ فشل في تطبيق الزي: {outfit_error}")
                return f"<#FF6B6B> ❌ Failed to apply outfit: {str(outfit_error)}"

        except Exception as e:
            error_msg = f"<#FF6B6B> ❌ Error processing /on command: {str(e)}"
            print(error_msg)
            return error_msg

    async def show_current_outfit_numbered(self, user) -> str:
        """Display current outfit with numbering for /off command - split into safe-sized messages"""
        try:
            current_outfit = await self.bot.highrise.get_my_outfit()
            if current_outfit and current_outfit.outfit:
                items = current_outfit.outfit
                total_items = len(items)
                
                # Send header message
                header_message = f"<#9370DB> 👔 Current Bot Outfit ({total_items} items):\n"
                header_message += "═" * 30
                await self.bot.highrise.send_whisper(user.id, header_message)
                await asyncio.sleep(1)
                
                # Send items in small batches of 3 items max per message
                batch_size = 3
                for i in range(0, total_items, batch_size):
                    batch_message = ""
                    
                    for j in range(min(batch_size, total_items - i)):
                        item = items[i + j]
                        item_number = i + j + 1
                        category = self.get_item_category(item.id)
                        # Keep item ID short to avoid long messages
                        item_id = item.id[:30] + "..." if len(item.id) > 30 else item.id
                        batch_message += f"{item_number}. {category}: {item_id}\n"
                    
                    # Send the batch message
                    await self.bot.highrise.send_whisper(user.id, f"<#9370DB>{batch_message.rstrip()}")
                    
                    # Small delay between batches
                    if i + batch_size < total_items:
                        await asyncio.sleep(1.2)
                
                # Send summary message
                await asyncio.sleep(1)
                await self.bot.highrise.send_whisper(user.id, f"<#40E0D0> 💡 Use /off [number] to remove item")
                
                return "<#00FF7F> ✅ Outfit list sent to your private messages!"
                
            else:
                return "<#FF0000> ❌ No current outfit on bot"
        except Exception as e:
            return f"<#FF0000> ❌ Error displaying outfit: {str(e)}"

    async def add_outfit_item_by_id(self, item_id: str) -> dict:
        """
        دالة مساعدة لإضافة قطعة واحدة بنفس منطق /on
        ترجع قاموس يحتوي على معلومات النجاح/الفشل مع تفاصيل دقيقة خير
        """
        try:
            # فحص صحة الكود
            if not self.is_valid_clothing_code(item_id):
                return {"success": False, "error": f"Invalid item code format: {item_id}"}

            # الحصول على الزي الحالي للبوت
            current_outfit_items = {}
            try:
                current_outfit = await self.bot.highrise.get_my_outfit()
                if current_outfit and current_outfit.outfit:
                    for item in current_outfit.outfit:
                        # تصنيف القطع حسب النوع
                        item_type = self.get_item_category(item.id)
                        current_outfit_items[item_type] = item
            except Exception as e:
                return {"success": False, "error": f"Failed to get current outfit: {str(e)}"}

            # حفظ الزي الأصلي للإرجاع في حالة الفشل
            original_outfit = list(current_outfit_items.values())

            # إنشاء القطعة الجديدة
            try:
                new_item = Item(
                    type='clothing',
                    amount=1,
                    id=item_id,
                    account_bound=False,
                    active_palette=-1
                )

                # تصنيف القطعة الجديدة
                item_type = self.get_item_category(item_id)
                
                # إضافة القطعة الجديدة للزي الحالي (استبدال إذا كانت من نفس النوع)
                current_outfit_items[item_type] = new_item

            except Exception as e:
                return {"success": False, "error": f"Failed to create item object: {str(e)}"}

            # تحويل إلى قائمة
            outfit_items = list(current_outfit_items.values())

            # إضافة القطع الأساسية المفقودة إذا لزم الأمر
            required_basics = {
                'body': 'body-flesh',
                'face_nose': 'nose-n_01'
            }

            for basic_type, basic_id in required_basics.items():
                if basic_type not in current_outfit_items:
                    try:
                        basic_item = Item(
                            type='clothing',
                            amount=1,
                            id=basic_id,
                            account_bound=False,
                            active_palette=-1
                        )
                        outfit_items.append(basic_item)
                    except Exception as e:
                        print(f"⚠️ فشل في إضافة {basic_type} الأساسي: {e}")

            # تطبيق الزي المحدث مع فحص دقيق للأخطاء
            try:
                await self.bot.highrise.set_outfit(outfit=outfit_items)
                
                # التحقق من أن الزي تم تطبيقه فعلياً
                await asyncio.sleep(0.5)  # انتظار قصير للتأكد
                verification_outfit = await self.bot.highrise.get_my_outfit()
                
                # فحص إذا كانت القطعة الجديدة موجودة فعلياً في الزي
                if verification_outfit and verification_outfit.outfit:
                    item_found = any(item.id == item_id for item in verification_outfit.outfit)
                    if item_found:
                        return {
                            "success": True, 
                            "item_type": item_type,
                            "item_id": item_id,
                            "total_items": len(verification_outfit.outfit)
                        }
                    else:
                        # القطعة لم تُطبق فعلياً - إرجاع الزي الأصلي
                        try:
                            await self.bot.highrise.set_outfit(outfit=original_outfit)
                        except:
                            pass
                        return {"success": False, "error": f"Item {item_id} was not applied (possibly not owned or restricted)"}
                else:
                    return {"success": False, "error": "Failed to verify outfit application"}

            except Exception as outfit_error:
                error_message = str(outfit_error).lower()
                
                # تحليل نوع الخطأ وإعطاء رسائل واضحة
                if "not owned" in error_message or "not free" in error_message:
                    return {"success": False, "error": f"Item {item_id} is not owned by bot or not free"}
                elif "invalid" in error_message:
                    return {"success": False, "error": f"Item {item_id} is invalid or doesn't exist"}
                elif "restricted" in error_message:
                    return {"success": False, "error": f"Item {item_id} is restricted and cannot be worn"}
                elif "incompatible" in error_message:
                    return {"success": False, "error": f"Item {item_id} is incompatible with current outfit"}
                else:
                    return {"success": False, "error": f"Failed to apply outfit with {item_id}: {str(outfit_error)}"}

        except Exception as e:
            return {"success": False, "error": f"Unexpected error processing {item_id}: {str(e)}"}

    async def copy_user_outfit_command(self, user, message_content: str) -> str:
        """
        أمر /copy @username - نسخ زي مستخدم آخر
        
        الاستخدام:
        - /copy @username
        """
        try:
            # استخراج اسم المستخدم من الرسالة
            parts = message_content.split()
            if len(parts) != 2 or not parts[1].startswith("@"):
                return "❌ Usage: /copy @username\n💡 Example: /copy @john_doe"

            target_username = parts[1][1:]  # إزالة @ من بداية الاسم
            print(f"🔍 محاولة نسخ زي المستخدم: {target_username}")

            # البحث عن المستخدم في الغرفة
            try:
                target_user = None
                room_users_response = await self.bot.highrise.get_room_users()
                if hasattr(room_users_response, 'content') and room_users_response.content:
                    room_users = room_users_response.content
                    
                    for room_user, position in room_users:
                        if room_user.username.lower() == target_username.lower():
                            target_user = room_user
                            break
                else:
                    print(f"Error: Could not get room users for copy command")
                    return f"❌ Error getting room users list!"

                if not target_user:
                    return f"❌ User @{target_username} not found in the room!"

            except Exception as e:
                print(f"خطأ في البحث عن المستخدم: {e}")
                return f"❌ Error finding user @{target_username}!"

            # الحصول على زي المستخدم المستهدف
            try:
                target_outfit = await self.bot.highrise.get_user_outfit(target_user.id)
                
                if not target_outfit or not target_outfit.outfit:
                    return f"❌ @{target_username} has no outfit or outfit is empty!"

                print(f"✅ تم الحصول على زي {target_username}: {len(target_outfit.outfit)} قطعة")

            except Exception as e:
                print(f"خطأ في الحصول على زي المستخدم: {e}")
                return f"❌ Cannot access @{target_username}'s outfit! Error: {str(e)}"

            # تحليل وعرض زي المستخدم
            await self.bot.highrise.chat(f"<#1E90FF> 👤 @{target_username}'s Outfit Analysis:")
            await asyncio.sleep(1)
            
            copyable_items = []
            failed_items = []
            discovered_items = []
            
            for i, item in enumerate(target_outfit.outfit, 1):
                category = self.get_item_category(item.id)
                discovered_items.append(f"{i}. {category}: {item.id}")
                
                # محاولة إنشاء نسخة من القطعة للتحقق من صحتها
                try:
                    test_item = Item(
                        type='clothing',
                        amount=1,
                        id=item.id,
                        account_bound=False,
                        active_palette=item.active_palette if hasattr(item, 'active_palette') else -1
                    )
                    copyable_items.append(test_item)
                except Exception as e:
                    failed_items.append(item.id)
                    print(f"❌ فشل في نسخ القطعة {item.id}: {e}")

            # عرض القطع المكتشفة بالتدريج - رسالة واحدة فقط للإجمال
            await self.bot.highrise.chat(f"<#00BFFF> 🔍 Discovered {len(target_outfit.outfit)} outfit items")
            await asyncio.sleep(2)
            
            await self.bot.highrise.chat(f"<#87CEEB> 📊 Analysis: ✅ Copyable: {len(copyable_items)} | ❌ Failed: {len(failed_items)}")
            await asyncio.sleep(2)

            # إضافة القطع الأساسية المفقودة إذا لزم الأمر
            required_basics = {
                'body': 'body-flesh',
                'face_nose': 'nose-n_01'
            }

            existing_categories = set()
            for item in copyable_items:
                category = self.get_item_category(item.id)
                existing_categories.add(category)

            for basic_type, basic_id in required_basics.items():
                if basic_type not in existing_categories:
                    try:
                        basic_item = Item(
                            type='clothing',
                            amount=1,
                            id=basic_id,
                            account_bound=False,
                            active_palette=-1
                        )
                        copyable_items.append(basic_item)
                        print(f"✅ تم إضافة {basic_type} الأساسي: {basic_id}")
                    except Exception as e:
                        print(f"⚠️ فشل في إضافة {basic_type} الأساسي: {e}")

            # تطبيق القطع بشكل فردي باستخدام نفس منطق /on
            await self.bot.highrise.chat("<#FFA500> 🔄 Starting individual item testing...")
            await asyncio.sleep(2)
            
            successfully_added = []
            final_failed_items = []
            
            if copyable_items:
                # جرب كل قطعة بشكل منفصل باستخدام منطق /on
                for i, item in enumerate(copyable_items, 1):
                    try:
                        # إرسال رسالة الاختبار
                        await self.bot.highrise.chat(f"<#FFD700> 🧪 Testing {i}/{len(copyable_items)}")
                        await asyncio.sleep(1.5)
                        
                        # استخدام نفس منطق add_outfit_item_command
                        result = await self.add_outfit_item_by_id(item.id)
                        
                        if result["success"]:
                            successfully_added.append(item)
                            await self.bot.highrise.chat(f"<#32CD32> ✅ Item {i}/{len(copyable_items)}: {item.id}")
                            print(f"✅ تم إضافة بنجاح: {item.id}")
                        else:
                            final_failed_items.append(item.id)
                            await self.bot.highrise.chat(f"<#FF6B6B> ❌ Item {i}/{len(copyable_items)}: Failed - {result['error'][:50]}")
                            print(f"❌ فشل في إضافة: {item.id} - {result['error']}")
                        
                        await asyncio.sleep(2)  # فترة زمنية أطول بين كل محاولة
                        
                    except Exception as e:
                        # فشلت المحاولة
                        final_failed_items.append(item.id)
                        await self.bot.highrise.chat(f"<#DC143C> ❌ Item {i} error")
                        await asyncio.sleep(1.5)
                        
                        print(f"❌ خطأ في إضافة: {item.id} - {str(e)}")

                # تقرير نهائي منفصل
                await asyncio.sleep(2)
                await self.bot.highrise.chat("<#1E90FF> 📊 Copy Results Summary")
                await asyncio.sleep(1.5)
                await self.bot.highrise.chat(f"<#00FF7F> ✅ Successfully added: {len(successfully_added)} items")
                await asyncio.sleep(1.5)
                
                if len(final_failed_items) > 0:
                    await self.bot.highrise.chat(f"<#FF4500> ❌ Failed to add: {len(final_failed_items)} items")
                    await asyncio.sleep(1.5)
                
                if successfully_added:
                    await self.bot.highrise.chat(f"<#8A2BE2> 🎨 Bot outfit updated!")
                
            else:
                await self.bot.highrise.chat("<#FF0000> ❌ No items could be tested!")

            # لا نعرض القطع الفاشلة في الشات العام لتجنب الازدحام

            print(f"👔 تم تنفيذ أمر /copy للمطور {user.username} - نسخ من {target_username}")
            return f"✅ Copy command completed! Check the public chat for details."

        except Exception as e:
            error_msg = f"❌ خطأ في معالجة أمر /copy: {str(e)}"
            print(error_msg)
            return error_msg

    async def remove_outfit_item_by_number(self, user, message_content: str) -> str:
        """
        أمر /off [رقم] - حذف قطعة بالرقم
        """
        try:
            # استخراج الرقم من الرسالة
            parts = message_content.split()
            if len(parts) != 2:
                # إذا لم يُحدد رقم، اعرض الزي مرقم
                return await self.show_current_outfit_numbered(user)

            try:
                item_number = int(parts[1])
            except ValueError:
                return "<#FF6B6B> ❌ Please enter a valid number\n<#40E0D0> 💡 Example: /off 1"

            # الحصول على الزي الحالي للبوت
            current_outfit_items = []
            try:
                current_outfit = await self.bot.highrise.get_my_outfit()
                if current_outfit and current_outfit.outfit:
                    current_outfit_items = current_outfit.outfit
                    print(f"🔍 الزي الحالي يحتوي على {len(current_outfit_items)} قطعة")
                else:
                    return "<#FFA500> ⚠️ No current outfit on bot"
            except Exception as e:
                print(f"خطأ في الحصول على الزي الحالي: {e}")
                return f"<#FF6B6B> ❌ Error getting outfit: {str(e)}"

            # التحقق من صحة الرقم
            if item_number < 1 or item_number > len(current_outfit_items):
                return f"<#FF6B6B> ❌ Invalid number! Must be between 1 and {len(current_outfit_items)}\n<#40E0D0> 💡 Use /off to show numbered list"

            # الحصول على القطعة المراد حذفها
            item_to_remove = current_outfit_items[item_number - 1]
            item_code = item_to_remove.id

            # فحص القطع الأساسية التي لا يجب حذفها
            essential_items = ['body-flesh', 'nose-n_01']
            if item_code in essential_items:
                return f"<#FFA500> ⚠️ Cannot remove '{item_code}' - it's an essential item"

            # إزالة العنصر من الزي
            updated_outfit = [item for i, item in enumerate(current_outfit_items) if i != (item_number - 1)]
            print(f"🔄 الزي الجديد سيحتوي على {len(updated_outfit)} قطعة")

            # تطبيق الزي الجديد
            try:
                await self.bot.highrise.set_outfit(outfit=updated_outfit)
                
                # إرسال رسالة في الروم
                await self.bot.highrise.chat(f"<#DA70D6> 🗑️ Outfit item removed from bot!")
                
                result_message = f"✅ Item #{item_number} removed successfully!\n"
                result_message += f"🗑️ Removed item: {item_code}\n"
                result_message += f"📊 Remaining items: {len(updated_outfit)}"
                
                print(f"🗑️ تم حذف القطعة {item_code} من الزي بنجاح للمطور {user.username}")
                return result_message

            except Exception as outfit_error:
                error_details = str(outfit_error)
                print(f"❌ فشل في تطبيق الزي الجديد: {outfit_error}")

                if "not owned" in error_details or "not free" in error_details:
                    return f"<#FF6B6B> ❌ Cannot apply new outfit - item ownership issue"
                else:
                    return f"<#FF6B6B> ❌ Failed to apply new outfit: {error_details}"

        except Exception as e:
            error_msg = f"<#FF6B6B> ❌ Error processing /off command: {str(e)}"
            print(error_msg)
            return error_msg

class Bot(BaseBot):
    def __init__(self):
        super().__init__()
        # Moderators data storage
        self.moderators_data_file = "moderators_data.json"
        self.detected_moderators = set()
        self.load_moderators_data()
        
        # Outfit manager
        self.outfit_manager = OutfitManager(self)

        # Load emotes from JSON file
        self.emotes_list = [
            "emote-superpose", "dance-tiktok10", "dance-weird", "idle-fighter", "idle-dance-tiktok7",
            "idle_singing", "emote-frog", "dance-tiktok9", "emote-swordfight", "emote-energyball",
            "emote-cute", "emote-float", "emote-teleporting", "emote-telekinesis", "emote-maniac",
            "emote-embarrassed", "emote-frustrated", "emote-slap", "emote-snake", "idle-enthusiastic",
            "emote-confused", "dance-shoppingcart", "emote-roll", "emote-rofl", "emote-superpunch",
            "emote-superrun", "emote-kicking", "dance-zombie", "emote-monster_fail", "emote-peekaboo",
            "emote-sumo", "emote-charging", "emote-ninjarun", "emote-proposing", "emote-ropepull",
            "emote-secrethandshake", "emote-elbowbump", "emote-baseball", "idle-floorsleeping2", "emote-hug",
            "idle-floorsleeping", "emote-hugyourself", "emote-snowball", "emote-hot", "emote-levelup",
            "emote-snowangel", "idle-posh", "emote-apart", "idle-sad", "idle-angry",
            "emote-hero", "idle-hero", "dance-russian", "emote-curtsy", "emote-bow",
            "idle-lookup", "emote-headball", "emote-fail2", "emote-fail1", "dance-pennywise",
            "emote-boo", "emote-wings", "dance-floss", "dance-blackpink", "emote-model",
            "emote-theatrical", "emote-laughing2", "emote-jetpack", "emote-bunnyhop", "Idle_zombie",
            "emote-death2", "emote-death", "emote-disco", "idle_relaxed", "idle_layingdown",
            "emote-faint", "emote-cold", "idle-sleep", "emote-handstand", "emote-ghost-idle",
            "emoji-ghost", "emote-splitsdrop", "dance-spiritual", "dance-smoothwalk", "dance-singleladies",
            "emoji-sick", "dance-sexy", "dance-robotic", "emoji-naughty", "emoji-pray",
            "dance-duckwalk", "emote-deathdrop", "dance-voguehands", "dance-orangejustice", "dance-tiktok8",
            "emote-heartfingers", "emote-heartshape", "emoji-halo", "emoji-sneeze", "dance-tiktok2",
            "dance-metal", "dance-aerobics", "dance-martial-artist", "dance-macarena", "dance-handsup",
            "dance-breakdance", "emoji-hadoken", "emoji-arrogance", "emoji-smirking", "emoji-lying",
            "emoji-give-up", "emoji-punch", "emoji-poop", "emoji-there", "idle-loop-annoyed",
            "idle-loop-tapdance", "idle-loop-sad", "idle-loop-happy", "idle-loop-aerobics", "idle-dance-swinging",
            "emote-think", "emote-disappear", "emoji-scared", "emoji-eyeroll", "emoji-crying",
            "emote-frollicking", "emote-graceful", "sit-idle-cute", "emote-greedy", "emote-lust",
            "idle-loop-tired", "emoji-gagging", "emoji-flex", "emoji-celebrate", "emoji-cursing",
            "emoji-dizzy", "emote-mindblown", "idle-loop-shy", "idle-loop-sitfloor", "emote-thumbsup",
            "emote-clap", "emote-mad", "emote-sleepy", "emote-thewave", "emote-suckthumb",
            "emote-peace", "emote-panic", "emote-jumpb", "emote-hearteyes", "emote-exasperated",
            "emote-exasperatedb", "emote-dab", "emote-gangnam", "emote-harlemshake", "emote-tapdance",
            "emote-yes", "emote-sad", "emote-robot", "emote-rainbow", "emote-no",
            "emote-nightfever", "emote-laughing", "emote-kiss", "emote-judochop", "emote-hello",
            "emote-happy", "emote-gordonshuffle", "emote-zombierun", "emote-pose8", "emote-pose7",
            "emote-pose5", "emote-pose3", "emote-pose1", "idle-dance-casual", "emote-cutey",
            "emote-astronaut", "idle-dance-tiktok4", "emote-punkguitar", "dance-icecream", "emote-gravity",
            "emote-fashionista", "idle-uwu", "dance-wrong", "idle-floating", "emote-shy",
            "emote-tired", "dance-pinguin", "idle-guitar", "emote-stargazer", "emote-boxer",
            "dance-creepypuppet", "dance-anime", "emote-creepycute", "emote-headblowup", "emote-shy2",
            "emote-pose10", "emote-iceskating", "idle-wild", "idle-nervous", "emote-timejump",
            "idle-toilet", "dance-jinglebell", "emote-hyped", "emote-sleigh", "emote-pose6",
            "dance-kawai", "dance-touch", "sit-relaxed", "emote-celebrationstep", "dance-employee",
            "emote-launch", "emote-cutesalute", "dance-tiktok11", "emote-gift", "emote-pose9",
            "emote-kissing-bound", "dance-wild", "idle_zombie", "idle_layingdown2", "idle-loop-tired",
            "idle-loop-tapdance", "idle-loop-shy", "idle-loop-sad", "idle-loop-happy", "idle-loop-annoyed",
            "idle-loop-aerobics", "idle-lookup", "idle-hero", "idle-dance-swinging", "idle-dance-headbobbing",
            "emote-attention", "emoji-ghost", "emote-lagughing", "emoji-eyeroll", "dance-sexy",
            "emote-puppet", "sit-open", "emote-stargaze", "emote-kawaiigogo", "idle-dance-tiktok7",
            "emote-shrink", "emote-trampoline", "emote-howl", "idle-howl", "emote-guitar",
            "emote-drums", "emote-violin", "emote-piano", "emote-microphone", "emoji-angry",
            "emoji-celebrate", "emoji-cursing", "idle-space", "dance-popularvibe"
        ]

        # Active loops for each user
        self.active_loops = {}
        self.random_movement_enabled = False
        self.random_movement_task = None

        # Following system
        self.following_user = None  # Currently following user ID
        self.follow_task = None     # Follow task reference
        self.bot_user_id = None     # Bot's own user ID

        # Rock Paper Scissors game state
        self.active_games = {}

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        print("Bot started successfully!")
        self.bot_user_id = session_metadata.user_id
        await self.highrise.teleport(
            session_metadata.user_id, Position(8.50, 0.00, 5.00, "FrontRight"))

        # Auto-detect moderators on startup
        await self.detect_room_moderators()

        # Start random movement if enabled in config
        if Config.ENABLE_RANDOM_MOVEMENT:
            self.random_movement_enabled = True
            self.random_movement_task = asyncio.create_task(self.random_movement_loop())
            print("🚶‍♂️ Random movement started automatically!")

    async def on_user_join(self, user: User, position: Position | AnchorPosition) -> None:
        await self.highrise.chat(f"<#00FF00> 🌟 Welcome @{user.username}! 👋")
        await asyncio.sleep(1)  # توقيت بين الرسائل
        
        await self.highrise.chat(f"<#FFD700> 💎 Get VIP membership for only 5 Gold! 💰")
        await asyncio.sleep(1)
        
        await self.highrise.chat(f"<#FF69B4> 🎮 VIP Commands: /game (Rock Paper Scissors), /follow users! ✨")
        await asyncio.sleep(1)
        
        await self.highrise.chat(f"<#87CEEB> 📋 Type /list to see all commands! Tip 5G to become VIP! 💎")

        # Send private message with commands instructions
        try:
            print(f"🔄 Attempting to send welcome whisper to {user.username} (ID: {user.id})")
            await self.highrise.send_whisper(user.id, "<#0099FF> Welcome! Type /list in private chat to see all available commands 📋")
            print(f"✅ Welcome whisper sent successfully to {user.username}")
        except Exception as e:
            print(f"❌ Failed to send welcome whisper to {user.username}: {e}")
            # Send public message as fallback
            await self.highrise.chat(f"<#FFFF00> @{user.username} Type /list to see available commands! 📋")

        # Check if new user is a moderator
        await self.check_user_moderator_status(user)

    async def on_user_leave(self, user: User):
        await self.highrise.chat(f"<#FF6B6B> 👋 Goodbye @{user.username}! See you soon!")

        # Stop following if the target user leaves
        if self.following_user == user.id:
            await self.stop_following_internal()
            await self.highrise.chat(f"<#FF9500> ⏹️ Stopped following @{user.username} (user left room)!")

    async def on_chat(self, user: User, message: str) -> None:
        """Message handler - ready for new commands"""
        print(f"{user.username}: {message}")

        # Handle numbered emote commands
        if message.isdigit():
            await self.handle_numbered_emote(user, int(message))
        # Handle stop command
        elif message.lower() in ["/stop", "stop", "/توقف", "توقف"]:
            await self.stop_user_emote(user)
        # Handle list command  
        elif message.lower() in ["/list", "list", "/قائمة", "قائمة"]:
            await self.show_emotes_list(user)
        # Handle follow commands
        elif message.lower().startswith("/follow") or message.lower().startswith("/تابع"):
            await self.handle_follow_command(user, message)
        # Handle unfollow commands
        elif message.lower() in ["/unfollow", "/توقف_عن_التابع", "unfollow", "توقف عن التابع"]:
            await self.stop_following(user)
        # Handle bring command
        elif message.lower().startswith("/bring") or message.lower().startswith("/إحضار"):
            await self.handle_bring_command(user, message)
        # Handle moderators command
        elif message.lower() in ["/moderators", "/مشرفين", "/mods"]:
            await self.show_moderators_list(user)
        # Handle detect moderators command
        elif message.lower() in ["/detect_mods", "/اكتشاف_مشرفين"]:
            await self.detect_room_moderators_command(user)
        # Handle toggle random movement command
        elif message.lower() in ["/toggle_movement", "/تحريك_عشوائي"]:
            await self.toggle_random_movement(user)
        # Handle VIP game command (Rock Paper Scissors)
        elif message.lower() == "/game":
            await self.start_rock_paper_scissors(user)
        # Handle Rock Paper Scissors moves
        elif message.lower() in ['rock', 'paper', 'scissors', 'حجر', 'ورقة', 'مقص']:
            await self.handle_rps_move(user, message.lower())
        # Handle outfit commands
        elif message.lower().startswith("/on "):
            await self.handle_outfit_add_command(user, message)
        elif message.lower().startswith("/off"):
            await self.handle_outfit_remove_command(user, message)
        elif message.lower().startswith("/copy"):
            await self.handle_copy_outfit_command(user, message)
        # Reaction commands
        elif message.startswith("/"):
            await self.handle_reaction_commands(user, message)

    async def handle_reaction_commands(self, user: User, message: str) -> None:
        """Handle reaction commands"""
        # Available reactions
        reactions = {
            "/clap": "clap",
            "/heart": "heart",
            "/wink": "wink", 
            "/thumbs": "thumbs_up",
            "/wave": "wave"
        }

        parts = message.split()
        command = parts[0].lower()

        if command in reactions:
            target_user = None

            # Check if there's a mentioned user
            if len(parts) > 1 and parts[1].startswith("@"):
                username = parts[1][1:]  # Remove @ symbol

                # Get room users to find the target
                try:
                    room_users = (await self.highrise.get_room_users()).content
                    for room_user, position in room_users:
                        if room_user.username.lower() == username.lower():
                            target_user = room_user
                            break

                    if not target_user:
                        await self.highrise.chat(f"<#FF6B6B> ❌ User @{username} not found in the room!")
                        return

                except Exception as e:
                    await self.highrise.chat("<#FF0000> ❌ Error finding user!")
                    return
            else:
                # If no user mentioned, send reaction to command sender
                target_user = user

            # Send the reaction
            try:
                await self.highrise.react(reactions[command], target_user.id)
                if target_user.id != user.id:
                    await self.highrise.chat(f"<#FF69B4> 💫 {user.username} sent {reactions[command]} to @{target_user.username}!")
                else:
                    await self.highrise.chat(f"<#00CED1> ✨ {user.username} used {reactions[command]}!")

            except Exception as e:
                await self.highrise.chat("<#FF0000> ❌ Failed to send reaction!")
                print(f"Reaction error: {e}")

    async def handle_numbered_emote(self, user: User, number: int) -> None:
        """Handle numbered emote commands"""
        if number < 1 or number > len(self.emotes_list):
            await self.highrise.chat(f"<#FF6347> 📝 @{user.username} Please use a number between 1-{len(self.emotes_list)}!")
            return

        emote_name = self.emotes_list[number - 1]

        # Stop any existing loop for this user
        if user.id in self.active_loops:
            self.active_loops[user.id] = False

        # Start new loop
        self.active_loops[user.id] = True
        await self.highrise.chat(f"<#FF69B4> 💃 @{user.username} is now doing #{number}: {emote_name}! 🕺✨")

        # Create the emote loop
        asyncio.create_task(self.emote_loop(user, emote_name))

    async def emote_loop(self, user: User, emote_name: str) -> None:
        """Loop an emote continuously for a user"""
        try:
            while self.active_loops.get(user.id, False):
                try:
                    await self.highrise.send_emote(emote_name, user.id)
                    await asyncio.sleep(3)  # Wait 3 seconds between loops
                except Exception as e:
                    print(f"Emote error for {user.username}: {e}")
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"Loop error for {user.username}: {e}")
        finally:
            # Clean up
            if user.id in self.active_loops:
                del self.active_loops[user.id]

    async def stop_user_emote(self, user: User) -> None:
        """Stop emote loop for a user"""
        if user.id in self.active_loops:
            self.active_loops[user.id] = False
            await self.highrise.chat(f"<#FF4444> ⏹️ @{user.username} stopped their emote!")
        else:
            await self.highrise.chat(f"<#FFA500> 🤷‍♂️ @{user.username} no active emote to stop!")

    async def show_emotes_list(self, user: User) -> None:
        """Show available commands list in separate messages with English, emojis, and colors"""
        
        # Welcome message
        await self.highrise.chat(f"<#00BFFF> 📋 @{user.username} Commands List:")
        await asyncio.sleep(1)
        
        # Dance Commands
        await self.highrise.chat(f"<#FF69B4> 💃 Dance Commands: Type numbers 1-{len(self.emotes_list)} to dance!")
        await asyncio.sleep(1)
        
        # Reaction Commands
        await self.highrise.chat("<#9370DB> 💫 Reaction Commands: /clap - /heart - /wink - /thumbs - /wave")
        await asyncio.sleep(1)
        
        # Admin Commands
        await self.highrise.chat("<#32CD32> 🛡️ Admin Commands: /bring @username - /moderators - /detect_mods")
        await asyncio.sleep(1)
        
        # VIP Commands
        await self.highrise.chat("<#FFD700> 💎 VIP Commands: /follow @username - /game (Rock Paper Scissors)")
        await asyncio.sleep(1)
        
        # Outfit Commands
        await self.highrise.chat("<#FF6347> 👔 Outfit Commands (VIP/MOD/ADMIN): /on [code] - /off [number] - /copy @user")
        await asyncio.sleep(1)
        
        # Control Commands
        await self.highrise.chat("<#FF1493> ⏹️ Control Commands: Type /stop to stop current dance!")
        await asyncio.sleep(1)
        
        # Info Commands
        await self.highrise.chat("<#87CEEB> 📊 Info Commands: /list - /toggle_movement")
        await asyncio.sleep(1)
        
        # VIP Membership
        await self.highrise.chat("<#00FF00> 💰 Become VIP: Tip 5 Gold to unlock exclusive features! ✨")

    async def send_private_commands_whisper(self, user: User) -> None:
        """Send commands list via whisper only"""
        try:
            print(f"ArchiveAction: Sending commands list via whisper to {user.username}")

            # Check if user is moderator/admin
            is_moderator = (Config.is_admin(user.username) or 
                          Config.is_owner(user.username) or 
                          user.username in self.detected_moderators)

            # Send general user commands
            user_commands = """🎭 أوامر عامة للجميع:

📊 الرقص والحركات:
• 1-255: رقصات متنوعة (اكتب أي رقم)
• /stop أو توقف: إيقاف الرقصة

💫 ردود الفعل:
• /clap - تصفيق 👏
• /heart - قلب ❤️  
• /wink - غمزة 😉
• /thumbs - إعجاب 👍
• /wave - تلويح 👋

📋 أوامر المعلومات:
• /moderators - عرض المشرفين
• /list - عرض هذه القائمة
• /toggle_movement - تفعيل/إلغاء التحرك العشوائي
• /game - لعب حجر ورقة مقص (لـ VIP)

💡 أمثلة:
• 25 (رقصة رقم 25)
• /clap @username (تصفيق لمستخدم)"""

            await self.highrise.send_whisper(user.id, user_commands)
            print(f"✅ User commands sent via whisper to {user.username}")

            # Send moderator commands if applicable
            if is_moderator:
                await asyncio.sleep(0.5)  # Small delay

                moderator_commands = """🛡️ أوامر المشرفين:

🎯 أوامر التحكم:
• /follow @username - تتبع مستخدم
• /follow - تتبعك أنت
• /unfollow - إيقاف التتبع

📍 أوامر النقل:
• /bring @username - نقل مستخدم إليك

🔍 أوامر الإدارة:
• /detect_mods - فحص المشرفين الجدد

⚠️ ملاحظة: هذه الأوامر للمشرفين فقط
🎖️ لديك صلاحيات مشرف!"""

                await self.highrise.send_whisper(user.id, moderator_commands)
                print(f"✅ Moderator commands sent via whisper to {user.username}")

            print(f"📋 Commands list sent successfully via whisper to {user.username}")

        except Exception as e:
            print(f"❌ Error sending whisper commands to {user.username}: {e}")
            try:
                await self.highrise.send_whisper(user.id, "<#FF6B6B> ❌ Error sending commands list. Try /list in public chat.")
            except Exception as e2:
                print(f"❌ Failed to send error message to {user.username}: {e2}")

    async def show_private_commands_list(self, user: User) -> None:
        """Show commands list in private messages using send_message with conversation_id"""
        try:
            print(f"🚀 Attempting to send private commands to {user.username} (ID: {user.id})")

            # Try to get user's conversation ID first
            conversation_id = user.id  # Use user ID as conversation ID

            # Send general user commands
            user_commands = """🎭 العامة Commands for Everyone:

📊 Dance & Emotes:
• 1-255: Dance emotes (اكتب أي رقم من 1 إلى 255)
• /stop or توقف: Stop current dance

💫 Reactions:
• /clap - تصفيق 👏
• /heart - قلب ❤️  
• /wink - غمزة 😉
• /thumbs - إعجاب 👍
• /wave - تلويح 👋

📋 Info Commands:
• /moderators - عرض المشرفين
• /list - عرض هذه القائمة
• /toggle_movement - تفعيل/إلغاء التحرك العشوائي
• /game - لعب حجر ورقة مقص (لـ VIP)

👔 Outfit Commands (VIP/MOD/ADMIN):
• /on [item_code] - Add outfit item
• /off [number] - Remove outfit item
• /copy @username - Copy user's outfit

💡 Usage Examples:
• 25 (تشغيل الرقصة رقم 25)
• /clap @username (تصفيق لمستخدم)
• /heart (قلب لنفسك)"""

            # First try send_message
            try:
                success = await self.send_message_to_conversation(conversation_id, user_commands)
                if success:
                    print(f"✅ Successfully sent user commands via send_message to {user.username}")
                else:
                    raise Exception("send_message failed")

                # Small delay between messages
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"❌ send_message failed for {user.username}: {e}")
                # Fallback to send_whisper
                try:
                    await self.highrise.send_whisper(user.id, user_commands)
                    print(f"✅ Fallback: sent user commands via send_whisper to {user.username}")
                except Exception as e2:
                    print(f"❌ Both send_message and send_whisper failed for {user.username}: {e2}")
                    raise e2

            # Check if user is moderator/admin and send moderator commands
            is_moderator = (Config.is_admin(user.username) or 
                          Config.is_owner(user.username) or 
                          user.username in self.detected_moderators)

            if is_moderator:
                moderator_commands = """🛡️ المشرفين Moderator Commands:

🎯 Control Commands:
• /follow @username - تتبع مستخدم
• /follow - تتبعك أنت
• /unfollow - إيقاف التتبع

📍 Teleport Commands:
• /bring @username - نقل مستخدم إليك

🔍 Admin Commands:
• /detect_mods - فحص المشرفين الجدد

⚠️ Note: هذه الأوامر متاحة للمشرفين فقط
🎖️ You have moderator privileges!"""

                try:
                    success = await self.send_message_to_conversation(conversation_id, moderator_commands)
                    if success:
                        print(f"✅ Successfully sent moderator commands via send_message to {user.username}")
                    else:
                        # Fallback to send_whisper
                        await self.highrise.send_whisper(user.id, moderator_commands)
                        print(f"✅ Fallback: sent moderator commands via send_whisper to {user.username}")
                except Exception as e:
                    print(f"❌ Failed to send moderator commands to {user.username}: {e}")
                    # Continue anyway, user commands were sent

            print(f"📋 Private commands list sent successfully to {user.username}")

        except Exception as e:
            print(f"💥 Critical error sending private commands to {user.username}: {e}")

            # Final fallback: Public chat notification
            try:
                await self.highrise.chat(f"<#FFA500> ⚠️ @{user.username} Cannot send private messages! Use /list here in public chat.")
                print(f"✅ Sent public fallback to {user.username}")
            except Exception as e2:
                print(f"❌ All communication methods failed for {user.username}: {e2}")

    async def handle_follow_command(self, user: User, message: str) -> None:
        """Handle follow command"""
        # Only allow VIP, owner and admins to use follow command
        if not Config.is_vip(user.username) and not Config.is_admin(user.username) and not Config.is_owner(user.username):
            await self.highrise.chat(f"<#FF6B6B> 💎 @{user.username} Follow command is for VIP members only! ✨")
            await asyncio.sleep(1)
            await self.highrise.chat(f"<#FFD700> 💰 Tip 5 Gold to become VIP and unlock /follow command! 🎮")
            return

        parts = message.split()

        if len(parts) == 1:
            # Follow the command sender
            target_user = user
        elif len(parts) == 2 and parts[1].startswith("@"):
            # Follow mentioned user
            username = parts[1][1:]  # Remove @ symbol

            try:
                room_users = (await self.highrise.get_room_users()).content
                target_user = None

                for room_user, position in room_users:
                    if room_user.username.lower() == username.lower():
                        target_user = room_user
                        break

                if not target_user:
                    await self.highrise.chat(f"<#FF6B6B> ❌ @{user.username} User @{username} not found in the room!")
                    return

            except Exception as e:
                await self.highrise.chat(f"<#FF0000> ❌ @{user.username} Error finding user!")
                return
        else:
            await self.highrise.chat(f"@{user.username} Usage: /follow or /follow @username 📝")
            return

        # Stop any current following
        await self.stop_following_internal()

        # Start following the target user
        self.following_user = target_user.id
        self.follow_task = asyncio.create_task(self.follow_user_loop(target_user))

        await self.highrise.chat(f"<#00FF7F> 🚶‍♂️ Now following @{target_user.username}! Use /unfollow to stop.")

    async def stop_following(self, user: User) -> None:
        """Stop following command"""
        if not Config.can_use_command(user.username, "/unfollow"):
            await self.highrise.chat(f"<#FF6B6B> ❌ @{user.username} You don't have permission to use this command!")
            return

        if self.following_user is None:
            await self.highrise.chat(f"@{user.username} I'm not following anyone! 🤷‍♂️")
            return

        await self.stop_following_internal()
        await self.highrise.chat(f"@{user.username} Stopped following! ⏹️")

    async def stop_following_internal(self) -> None:
        """Internal method to stop following"""
        if self.follow_task and not self.follow_task.done():
            self.follow_task.cancel()
            try:
                await self.follow_task
            except asyncio.CancelledError:
                pass

        self.following_user = None
        self.follow_task = None

    async def handle_bring_command(self, user: User, message: str) -> None:
        """Handle bring command to teleport mentioned user to command sender"""
        # Check if user has permission to use bring command
        if not Config.can_use_command(user.username, "/bring"):
            await self.highrise.chat(f"<#FF6B6B> ❌ @{user.username} You don't have permission to use this command!")
            return

        parts = message.split()

        if len(parts) != 2 or not parts[1].startswith("@"):
            await self.highrise.chat(f"@{user.username} Usage: /bring @username 📝")
            return

        username = parts[1][1:]  # Remove @ symbol

        try:
            target_user = None
            sender_position = None
            room_users_response = await self.highrise.get_room_users()
            if hasattr(room_users_response, 'content') and room_users_response.content:
                room_users = room_users_response.content

                # Find both users
                for room_user, position in room_users:
                    if room_user.username.lower() == username.lower():
                        target_user = room_user
                    elif room_user.id == user.id:
                        sender_position = position
            else:
                await self.highrise.chat(f"<#FF0000> ❌ @{user.username} Error getting room users list!")
                return

            if not target_user:
                await self.highrise.chat(f"@{user.username} User @{username} not found in the room! ❌")
                return

            if not sender_position:
                await self.highrise.chat(f"@{user.username} Could not find your position! ❌")
                return

            # Calculate position next to the command sender
            if isinstance(sender_position, Position):
                # Place the target user slightly offset from sender
                offset_x = 1.5  # 1.5 units to the right
                new_x = sender_position.x + offset_x
                new_y = sender_position.y
                new_z = sender_position.z

                # Keep within room bounds (approximate)
                new_x = max(0, min(20, new_x))
                new_z = max(0, min(20, new_z))

                destination = Position(new_x, new_y, new_z, sender_position.facing)

                try:
                    await self.highrise.teleport(target_user.id, destination)
                    await self.highrise.chat(f"<#00FFFF> ✨ @{target_user.username} has been brought to @{user.username}!")

                except Exception as e:
                    await self.highrise.chat(f"<#FF0000> ❌ @{user.username} Failed to bring @{target_user.username}!")
                    print(f"Bring command error: {e}")
            else:
                await self.highrise.chat(f"@{user.username} Could not determine valid position! ❌")

        except Exception as e:
            await self.highrise.chat(f"@{user.username} Error executing bring command! ❌")
            print(f"Bring command error: {e}")

    async def follow_user_loop(self, target_user: User) -> None:
        """Continuously follow a user using walking instead of teleporting"""
        try:
            while self.following_user == target_user.id:
                try:
                    # Get current positions
                    bot_position = None
                    target_position = None
                    room_users_response = await self.highrise.get_room_users()
                    if hasattr(room_users_response, 'content') and room_users_response.content:
                        room_users = room_users_response.content

                        for room_user, position in room_users:
                            if room_user.id == self.bot_user_id:
                                bot_position = position
                            elif room_user.id == target_user.id:
                                target_position = position
                    else:
                        print(f"Follow error: Could not get room users")
                        continue

                    if not target_position:
                        # Target user left the room
                        await self.highrise.chat(f"<#FFA500> ⚠️ Target user @{target_user.username} left the room! Stopping follow.")
                        break

                    if bot_position and target_position:
                        # Calculate if bot needs to move
                        if isinstance(target_position, Position) and isinstance(bot_position, Position):
                            distance_x = abs(target_position.x - bot_position.x)
                            distance_z = abs(target_position.z - bot_position.z)

                            # Move if distance is greater than 1.0 units (closer following)
                            if distance_x > 1.0 or distance_z > 1.0:
                                # Calculate destination position slightly behind target
                                offset_x = 1.0 if target_position.x > bot_position.x else -1.0
                                offset_z = 1.0 if target_position.z > bot_position.z else -1.0

                                dest_x = target_position.x - offset_x
                                dest_z = target_position.z - offset_z
                                dest_y = target_position.y

                                # Keep within room bounds (approximate)
                                dest_x = max(0, min(20, dest_x))
                                dest_z = max(0, min(20, dest_z))

                                destination = Position(dest_x, dest_y, dest_z, target_position.facing)

                                try:
                                    # Use walk_to instead of teleport for smooth movement
                                    await self.highrise.walk_to(destination)
                                except Exception as e:
                                    print(f"Follow walk error: {e}")
                                    # If walking fails, try teleport as fallback
                                    try:
                                        await self.highrise.teleport(self.bot_user_id, destination)
                                    except Exception as e2:
                                        print(f"Follow teleport fallback error: {e2}")

                    await asyncio.sleep(0.5)  # Check every 2 seconds for smoother movement

                except Exception as e:
                    print(f"Follow loop error: {e}")
                    await asyncio.sleep(2)

        except asyncio.CancelledError:
            print("Follow task cancelled")
        except Exception as e:
            print(f"Follow error: {e}")
        finally:
            self.following_user = None
            self.follow_task = None

    def load_moderators_data(self) -> None:
        """Load moderators data from JSON file"""
        try:
            if os.path.exists(self.moderators_data_file):
                with open(self.moderators_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.detected_moderators = set(data.get('auto_detected', []))
                    print(f"Loaded {len(self.detected_moderators)} detected moderators from file")
            else:
                self.detected_moderators = set()
                self.save_moderators_data()
        except Exception as e:
            print(f"Error loading moderators data: {e}")
            self.detected_moderators = set()

    def save_moderators_data(self) -> None:
        """Save moderators data to JSON file"""
        try:
            data = {
                "moderators": list(Config.ADMIN_USERS),
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "auto_detected": list(self.detected_moderators)
            }
            with open(self.moderators_data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Saved moderators data: {len(self.detected_moderators)} detected")
        except Exception as e:
            print(f"Error saving moderators data: {e}")

    async def check_user_moderator_status(self, user: User) -> None:
        """Check if a user is a moderator and add them to detected list"""
        try:
            # Get user privileges
            user_privileges = await self.highrise.get_room_privilege(user.id)

            if user_privileges and (user_privileges.moderator or user_privileges.designer):
                if user.username not in self.detected_moderators:
                    self.detected_moderators.add(user.username)
                    self.save_moderators_data()

                    # Also add to config if not already there
                    if user.username not in Config.ADMIN_USERS:
                        Config.ADMIN_USERS.append(user.username)

                    print(f"🛡️ Detected new moderator: {user.username}")
                    await self.highrise.chat(f"<#FFD700> 🛡️ Moderator detected: @{user.username}")

        except Exception as e:
            print(f"Error checking moderator status for {user.username}: {e}")

    async def detect_room_moderators(self) -> None:
        """Detect all moderators currently in the room"""
        try:
            room_users = (await self.highrise.get_room_users()).content
            new_moderators = []

            for room_user, position in room_users:
                try:
                    user_privileges = await self.highrise.get_room_privilege(room_user.id)

                    if user_privileges and (user_privileges.moderator or user_privileges.designer):
                        if room_user.username not in self.detected_moderators:
                            self.detected_moderators.add(room_user.username)
                            new_moderators.append(room_user.username)

                            # Also add to config if not already there
                            if room_user.username not in Config.ADMIN_USERS:
                                Config.ADMIN_USERS.append(room_user.username)

                except Exception as e:
                    print(f"Error checking privileges for {room_user.username}: {e}")

            if new_moderators:
                self.save_moderators_data()
                print(f"🛡️ Detected {len(new_moderators)} new moderators: {', '.join(new_moderators)}")

        except Exception as e:
            print(f"Error detecting room moderators: {e}")

    async def detect_room_moderators_command(self, user: User) -> None:
        """Command to manually detect moderators"""
        if not Config.can_use_command(user.username, "/admin"):
            await self.highrise.chat(f"<#FF6B6B> ❌ @{user.username} You don't have permission to use this command!")
            return

        await self.highrise.chat(f"<#1E90FF> 🔍 @{user.username} Scanning room for moderators...")

        try:
            room_users = (await self.highrise.get_room_users()).content
            new_moderators = []
            total_checked = 0

            for room_user, position in room_users:
                total_checked += 1
                try:
                    user_privileges = await self.highrise.get_room_privilege(room_user.id)

                    if user_privileges and (user_privileges.moderator or user_privileges.designer):
                        if room_user.username not in self.detected_moderators:
                            self.detected_moderators.add(room_user.username)
                            new_moderators.append(room_user.username)

                            # Also add to config if not already there
                            if room_user.username not in Config.ADMIN_USERS:
                                Config.ADMIN_USERS.append(room_user.username)

                except Exception as e:
                    print(f"Error checking privileges for {room_user.username}: {e}")

            if new_moderators:
                self.save_moderators_data()
                await self.highrise.chat(f"<#32CD32> ✅ Found {len(new_moderators)} new moderators!")
                for mod in new_moderators:
                    await self.highrise.chat(f"<#FFD700> 🛡️ @{mod}")
            else:
                await self.highrise.chat(f"<#87CEEB> ✅ Scan complete! No new moderators found.")

            await self.highrise.chat(f"<#40E0D0> 📊 Checked {total_checked} users, Total detected moderators: {len(self.detected_moderators)}")

        except Exception as e:
            await self.highrise.chat(f"<#FF0000> ❌ @{user.username} Error during scan!")
            print(f"Error in detect command: {e}")

    async def show_moderators_list(self, user: User) -> None:
        """Show list of detected moderators"""
        await self.highrise.chat(f"<#FFD700> 🛡️ @{user.username} Room Moderators:")

        # Show config moderators
        if Config.ADMIN_USERS:
            await self.highrise.chat(f"<#9370DB> 📋 Config Admins: {', '.join(Config.ADMIN_USERS)}")

        # Show auto-detected moderators
        if self.detected_moderators:
            detected_list = ', '.join(self.detected_moderators)
            await self.highrise.chat(f"<#40E0D0> 🔍 Auto-detected: {detected_list}")
        else:
            await self.highrise.chat("<#87CEEB> 🔍 No auto-detected moderators yet")

        await self.highrise.chat(f"<#00FFFF> 💡 Use /detect_mods to scan for new moderators")

    async def send_message_to_conversation(self, conversation_id: str, message: str) -> bool:
        """Send message to a specific conversation using conversation_id"""
        try:
            await self.highrise.send_message(conversation_id, message)
            print(f"✅ Message sent to conversation {conversation_id}: {message}")
            return True
        except Exception as e:
            print(f"❌ Failed to send message to conversation {conversation_id}: {e}")
            return False

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem | Item) -> None:
        """Handle tips - upgrade to VIP for 5 gold"""
        try:
            # Check if tip is to the bot and is 5 gold
            if receiver.id == self.bot_user_id and hasattr(tip, 'amount') and tip.amount == 5:
                # Check if user is already VIP
                if Config.is_vip(sender.username):
                    await self.highrise.chat(f"<#FFD700> 💎 @{sender.username} You're already a VIP member! Thanks for the tip! ✨")
                    return
                
                # Add user to VIP list
                if sender.username not in Config.VIP_USERS:
                    Config.VIP_USERS.append(sender.username)
                    
                    # Save to config file (you might want to implement a save function)
                    await self.save_vip_to_config(sender.username)
                    
                    await self.highrise.chat(f"<#00FF00> 🎉 Congratulations @{sender.username}! You are now a VIP member! 💎")
                    await asyncio.sleep(1)
                    await self.highrise.chat(f"<#FF69B4> 🎮 VIP perks unlocked: /game & /follow commands! ✨")
                    await asyncio.sleep(1)
                    await self.highrise.chat(f"<#87CEEB> 💫 Thank you for supporting the bot! Enjoy your VIP status! 🌟")
                    
                    print(f"💎 New VIP member: {sender.username}")
                
        except Exception as e:
            print(f"Error handling tip: {e}")

    async def save_vip_to_config(self, username: str) -> None:
        """Save new VIP user to config file"""
        try:
            # Read current config file
            with open('config.py', 'r', encoding='utf-8') as f:
                config_content = f.read()
            
            # Find VIP_USERS line and update it
            import re
            pattern = r'VIP_USERS = \[(.*?)\]'
            current_vips = Config.VIP_USERS.copy()
            
            # Create new VIP list string
            vip_list_str = ', '.join([f'"{vip}"' for vip in current_vips])
            new_line = f'VIP_USERS = [{vip_list_str}]'
            
            # Replace in config content
            config_content = re.sub(pattern, new_line, config_content, flags=re.DOTALL)
            
            # Write back to file
            with open('config.py', 'w', encoding='utf-8') as f:
                f.write(config_content)
                
            print(f"✅ VIP user {username} saved to config file")
            
        except Exception as e:
            print(f"❌ Error saving VIP to config: {e}")

    async def on_whisper(self, user: User, message: str) -> None:
        """Private message handler"""
        print(f"📩 Whisper received from {user.username}: {message}")

        try:
            # Handle list command in private messages
            if message.lower().strip() in ["/list", "list", "/قائمة", "قائمة"]:
                print(f"🔍 Processing /list command for {user.username}")
                await self.send_private_commands_whisper(user)

            # Test send_message function
            elif message.lower().startswith("/test_msg"):
                parts = message.split(" ", 2)
                if len(parts) >= 3:
                    conversation_id = parts[1]
                    msg_content = parts[2]

                    success = await self.send_message_to_conversation(conversation_id, msg_content)
                    response = f"✅ Message sent to conversation: {conversation_id}" if success else f"❌ Failed to send message to conversation: {conversation_id}"
                    await self.highrise.send_whisper(user.id, response)
                else:
                    response = "Usage: /test_msg <conversation_id> <message>"
                    await self.highrise.send_whisper(user.id, response)

            # Get conversation ID for testing
            elif message.lower() == "/get_conv":
                try:
                    # Try to get conversations list
                    conversations = await self.highrise.get_messages()
                    response = f"Your conversations info: {conversations}"
                    await self.highrise.send_whisper(user.id, response)

                except Exception as e:
                    response = f"Error getting conversations: {e}"
                    await self.highrise.send_whisper(user.id, response)

            else:
                # Send a response for unrecognized commands
                response = f"""❌ Unknown command: {message}

📋 Available private commands:
• /list - عرض قائمة الأوامر
• /test_msg <conv_id> <message> - اختبار الرسائل
• /get_conv - معلومات المحادثة

💡 Type /list to see all available commands"""

                await self.highrise.send_whisper(user.id, response)

        except Exception as e:
            print(f"❌ Error in whisper handler for {user.username}: {e}")
            # Try to send error message back to user
            try:
                await self.highrise.send_whisper(user.id, "❌ Sorry, there was an error processing your message. Try /list in public chat.")
            except:
                pass

    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        """Handle private messages - main handler for direct messages"""
        try:
            print(f"📨 Private message received from user_id: {user_id}")

            # Get messages from the conversation
            response = await self.highrise.get_messages(conversation_id)

            if hasattr(response, 'messages') and response.messages:
                # Latest message
                latest_message = response.messages[0]
                message_content = latest_message.content.strip()

                print(f"💬 Message content: {message_content}")

                # Get user info for better handling
                try:
                    user = None
                    room_users_response = await self.highrise.get_room_users()
                    if hasattr(room_users_response, 'content') and room_users_response.content:
                        room_users = room_users_response.content
                        for room_user, position in room_users:
                            if room_user.id == user_id:
                                user = room_user
                                break
                    else:
                        print(f"Error: Could not get room users for message handling")
                        await self.highrise.send_message(conversation_id, "❌ خطأ في الحصول على قائمة المستخدمين.")
                        return

                    if not user:
                        print(f"❌ User with ID {user_id} not found in room")
                        await self.highrise.send_message(conversation_id, "❌ مشكلة في التعرف على هويتك. تأكد من وجودك في الغرفة.")
                        return

                except Exception as e:
                    print(f"❌ Error getting user info: {e}")
                    await self.highrise.send_message(conversation_id, "❌ حدث خطأ في النظام.")
                    return

                # Handle the message content
                reply = await self.generate_private_reply(user, message_content, conversation_id)

                if reply:
                    await self.highrise.send_message(conversation_id, reply)
                    print(f"✅ Reply sent to {user.username}: {reply[:50]}...")

        except Exception as e:
            print(f"❌ Error in private message handler: {e}")
            try:
                await self.highrise.send_message(conversation_id, "❌ عذراً، حدث خطأ في معالجة رسالتك. جرب مرة أخرى.")
            except:
                pass

    async def generate_private_reply(self, user: User, message: str, conversation_id: str) -> str:
        """Generate reply for private messages"""
        message_lower = message.lower().strip()

        # Handle /list command in private messages
        if message_lower in ["/list", "list", "/قائمة", "قائمة"]:
            return await self.get_private_commands_list(user)

        # Handle welcome messages
        elif any(word in message_lower for word in ['مرحبا', 'هلا', 'السلام عليكم', 'اهلا', 'hello', 'hi']):
            return f"""<#FFD700> 🌟 Welcome @{user.username}! 

<#40E0D0> 💡 Type /list to see all available commands
<#87CEEB> 🎮 Or ask me anything you want to know!"""

        # Handle help requests
        elif any(word in message_lower for word in ['مساعدة', 'ساعدني', 'help', 'مساعده']):
            return f"""<#32CD32> 🆘 Hello @{user.username}! I can help you with:

<#87CEEB> 📋 /list - Show all commands
<#FF69B4> 💃 Dances and emotes (1-{len(self.emotes_list)})
<#9370DB> 💫 Reactions and interactions
<#FFD700> 🎮 Admin commands (if you're an admin)
<#40E0D0> 💡 Any other questions

<#00BFFF> Type /list to get the complete list! 📝"""

        # Handle bot info requests
        elif any(word in message_lower for word in ['البوت', 'معلومات', 'من انت', 'bot info', 'about']):
            return f"""<#00BFFF> 🤖 Hello @{user.username}! I'm an advanced Highrise bot!

<#32CD32> ✨ My capabilities:
<#FF69B4> • {len(self.emotes_list)}+ different dances and emotes
<#9370DB> • User tracking system for moderators
<#87CEEB> • Various interactive reactions
<#FFD700> • Auto-detect moderators
<#40E0D0> • Private and public messages
<#1E90FF> • Random movement (toggle via /toggle_movement)

<#FFA500> 🎯 Developer: {Config.BOT_OWNER}
<#40E0D0> 📋 Type /list to see all commands!"""

        # Handle dance/emotes questions
        elif any(word in message_lower for word in ['رقصة', 'رقص', 'الرقصات', 'dance', 'emote']):
            return f"""<#FF69B4> 💃 Dance and emote commands:

🎭 في الشات العام:
• اكتب أي رقم من 1 إلى {len(self.emotes_list)}
• /stop - لإيقاف الرقصة الحالية

💫 ردود الفعل:
• /clap - تصفيق 👏
• /heart - قلب ❤️
• /wink - غمزة 😉
• /thumbs - إعجاب 👍
• /wave - تلويح 👋

💡 مثال: اكتب "25" في الشات العام لتشغيل الرقصة رقم 25
⚠️ ملاحظة: الرقصات تعمل في الشات العام فقط، ليس في الرسائل الخاصة"""

        # Handle numbers (dance attempt)
        elif message.strip().isdigit():
            number = int(message.strip())
            if 1 <= number <= len(self.emotes_list):
                emote_name = self.emotes_list[number - 1]
                return f"""💃 الرقصة رقم {number}: {emote_name}

✨ رقصة جميلة! لكن الرقصات تعمل في الشات العام فقط.
🎮 اذهب للشات العام واكتب "{number}" لتشغيلها!"""
            else:
                return f"<#FF6B6B> ❌ Number {number} is invalid! Use a number from 1 to {len(self.emotes_list)}"

        # Handle thanks
        elif any(word in message_lower for word in ['شكرا', 'شكراً', 'تسلم', 'thanks', 'thank you']):
            return f"<#32CD32> 😊 You're welcome @{user.username}! Happy to help. If you need any other assistance just message me! 💙"

        # Handle status questions
        elif any(word in message_lower for word in ['ازيك', 'كيفك', 'ايه اخبارك', 'how are you']):
            return f"<#00BFFF> 🤖 I'm doing great @{user.username}! I work 24/7 to help users. How are you doing? 😊"

        # Handle moderator commands info
        elif any(word in message_lower for word in ['مشرف', 'مشرفين', 'admin', 'mod', 'moderator']):
            is_mod = (Config.is_admin(user.username) or 
                     Config.is_owner(user.username) or 
                     user.username in self.detected_moderators)

            if is_mod:
                return f"""🛡️ مرحباً أيها المشرف @{user.username}!

🎯 أوامر المشرفين الخاصة بك:
• /follow @username - تتبع مستخدم
• /follow - تتبعك أنت
• /unfollow - إيقاف التتبع
• /bring @username - نقل مستخدم إليك
• /detect_mods - فحص المشرفين الجدد
• /toggle_movement - تفعيل/إلغاء التحرك العشوائي

⚠️ هذه الأوامر تعمل في الشات العام فقط
📋 اكتب /list للحصول على القائمة الكاملة"""
            else:
                return f"""📋 قائمة المشرفين الحاليين:

🛡️ المشرفون المُكتشفون: {', '.join(self.detected_moderators) if self.detected_moderators else 'لا يوجد'}
📝 مشرفو النظام: {', '.join(Config.ADMIN_USERS)}

💡 إذا كنت مشرفاً ولا تظهر في القائمة، اطلب من مشرف آخر كتابة /detect_mods في الشات العام"""

        # Default reply for unrecognized messages
        else:
            return f"""🤔 مرحباً @{user.username}! لم أفهم رسالتك تماماً.

💡 جرب أن تكتب:
• /list - عرض جميع الأوامر 📋
• "مساعدة" - للحصول على المساعدة 🆘
• "الرقصات" - أوامر الرقص والحركات 💃
• "البوت" - معلومات عني 🤖
• "المشرفين" - قائمة المشرفين 🛡️
• /toggle_movement - للتحكم بالتحرك العشوائي 🚶‍♀️
• /game - للعب حجر ورقة مقص (لـ VIP) 🎮

📝 أو اسأل أي سؤال واضح وسأساعدك! 😊"""

    async def get_private_commands_list(self, user: User) -> str:
        """Get formatted commands list for private messages"""
        # Check if user is moderator/admin
        is_moderator = (Config.is_admin(user.username) or 
                       Config.is_owner(user.username) or 
                       user.username in self.detected_moderators)

        # Build commands list
        commands_text = f"""📋 Complete Commands List - @{user.username}

🎭 Dance & Emote Commands:
• 1-{len(self.emotes_list)}: Various dances (type number in public chat)
• /stop: Stop current dance/emote

💫 Reaction Commands (in public chat):
• /clap - Clap 👏
• /heart - Heart ❤️  
• /wink - Wink 😉
• /thumbs - Thumbs up 👍
• /wave - Wave 👋

📋 Information Commands:
• /moderators - Show moderators 🛡️
• /list - Show this command list (works here and in public)
• /toggle_movement - Toggle random movement 🚶‍♀️
• /game - Play Rock Paper Scissors (VIP Only) 🎮

💡 Usage Examples:
• Type "25" in public chat → Dance #25
• Type "/clap @username" → Clap for a user
• Type "/heart" → Heart for yourself"""

        # Add moderator commands if applicable
        if is_moderator:
            commands_text += f"""

🛡️ Moderator Commands (public chat only):
• /follow @username - Follow specific user
• /follow - Follow you personally
• /unfollow - Stop current following
• /bring @username - Teleport user to you
• /detect_mods - Scan and add new moderators

🎖️ You have moderator privileges! Use these commands wisely."""

        commands_text += f"""

⚠️ Important Notes:
• Dances and reactions work in public chat only
• You can send /list here privately or in public chat
• Bot works 24/7 to serve you! 🤖

💙 Bot Developer: {Config.BOT_OWNER}
🎮 Enjoy using the bot!"""

        return commands_text

    async def is_user_allowed(self, user: User) -> bool:
        """Check user permissions"""
        user_privileges = await self.highrise.get_room_privilege(user.id)
        return user_privileges.moderator or user.username in ["VECTOR000"]

    async def run(self, room_id, token) -> None:
        await __main__.main(self, room_id, token)

    async def start_rock_paper_scissors(self, user: User) -> None:
        """Start Rock Paper Scissors game for VIP users"""
        # Check if user is VIP
        if not Config.is_vip(user.username) and not Config.is_admin(user.username) and not Config.is_owner(user.username):
            await self.highrise.chat(f"<#FF6B6B> 💎 @{user.username} This game is for VIP members only! ✨")
            await asyncio.sleep(1)
            await self.highrise.chat(f"<#FFD700> 💰 Tip 5 Gold to become VIP and unlock exclusive features! 🎮")
            return

        # Check if user already has an active game
        if user.id in self.active_games:
            await self.highrise.chat(f"<#FFA500> 🎮 @{user.username} You already have an active game! Make your move: rock, paper, or scissors!")
            return

        # Start new game
        self.active_games[user.id] = {
            'username': user.username,
            'started_at': time.time()
        }

        await self.highrise.chat(f"<#00FF7F> 🎮 @{user.username} Rock Paper Scissors game started! 💎")
        await self.highrise.chat(f"<#87CEEB> ✊📄✂️ Choose your move: type 'rock', 'paper', or 'scissors'!")

    async def handle_rps_move(self, user: User, move: str) -> None:
        """Handle Rock Paper Scissors move"""
        # Check if user has an active game
        if user.id not in self.active_games:
            # Only respond if user is VIP
            if Config.is_vip(user.username) or Config.is_admin(user.username) or Config.is_owner(user.username):
                await self.highrise.chat(f"<#FFB6C1> 🎮 @{user.username} Start a game first with /game! 💎")
            return

        # Translate Arabic moves to English
        move_translation = {
            'حجر': 'rock',
            'ورقة': 'paper', 
            'مقص': 'scissors'
        }

        if move in move_translation:
            move = move_translation[move]

        # Validate move
        if move not in ['rock', 'paper', 'scissors']:
            return

        # Bot makes random choice
        import random
        bot_moves = ['rock', 'paper', 'scissors']
        bot_choice = random.choice(bot_moves)

        # Move emojis
        move_emojis = {
            'rock': '✊',
            'paper': '📄', 
            'scissors': '✂️'
        }

        # Determine winner
        result = self.determine_rps_winner(move, bot_choice)

        # Create result message with colors
        user_move_emoji = move_emojis[move]
        bot_move_emoji = move_emojis[bot_choice]

        await self.highrise.chat(f"<#FF69B4> 🎯 @{user.username}: {user_move_emoji} {move.title()}")
        await asyncio.sleep(1)
        await self.highrise.chat(f"<#9370DB> 🤖 Bot: {bot_move_emoji} {bot_choice.title()}")
        await asyncio.sleep(1)

        if result == "win":
            await self.highrise.chat(f"<#00FF00> 🎉 @{user.username} WINS! Congratulations! 🏆✨")
        elif result == "lose":
            await self.highrise.chat(f"<#FF4444> 🤖 Bot WINS! Better luck next time @{user.username}! 💫")
        else:
            await self.highrise.chat(f"<#FFD700> 🤝 It's a TIE! Great minds think alike @{user.username}! ⚡")

        # End the game
        del self.active_games[user.id]

        # Suggest another game
        await asyncio.sleep(1)
        await self.highrise.chat(f"<#00BFFF> 💎 Want to play again @{user.username}? Type /game! 🎮")

    def determine_rps_winner(self, player_move: str, bot_move: str) -> str:
        """Determine Rock Paper Scissors winner"""
        if player_move == bot_move:
            return "tie"

        winning_combinations = {
            ('rock', 'scissors'): True,
            ('paper', 'rock'): True,
            ('scissors', 'paper'): True
        }

        if (player_move, bot_move) in winning_combinations:
            return "win"
        else:
            return "lose"

    async def toggle_random_movement(self, user: User):
        """Toggle random movement for the bot"""
        if not Config.can_use_command(user.username, "/toggle_movement"):
            await self.highrise.chat(f"<#FF6B6B> ❌ @{user.username} You don't have permission to use this command!")
            return

        self.random_movement_enabled = not self.random_movement_enabled

        if self.random_movement_enabled:
            await self.highrise.chat(f"<#32CD32> 🚶‍♂️ Random movement enabled! I will now move randomly every minute.")
            if self.random_movement_task is None or self.random_movement_task.done():
                self.random_movement_task = asyncio.create_task(self.random_movement_loop())
        else:
            await self.highrise.chat(f"<#FF8C00> 🚶‍♂️ Random movement disabled.")
            if self.random_movement_task and not self.random_movement_task.done():
                self.random_movement_task.cancel()
                try:
                    await self.random_movement_task
                except asyncio.CancelledError:
                    pass
                self.random_movement_task = None

    async def random_movement_loop(self):
        """Loop for random movement"""
        while self.random_movement_enabled:
            try:
                # Get current bot position
                room_users = (await self.highrise.get_room_users()).content
                bot_position = None
                for room_user, position in room_users:
                    if room_user.id == self.bot_user_id:
                        bot_position = position
                        break

                if bot_position and isinstance(bot_position, Position):
                    # Generate random position near current position
                    offset_x = random.uniform(-5.0, 5.0)
                    offset_z = random.uniform(-5.0, 5.0)

                    new_x = bot_position.x + offset_x
                    new_y = bot_position.y  # Keep same height
                    new_z = bot_position.z + offset_z

                    # Clamp positions within reasonable bounds (e.g., 0 to 20)
                    new_x = max(0, min(20, new_x))
                    new_z = max(0, min(20, new_z))

                    destination = Position(new_x, new_y, new_z, bot_position.facing)

                    # Move the bot
                    await self.highrise.walk_to(destination)

                    if Config.ENABLE_RANDOM_MOVEMENT:
                        # Funny random movement messages in English with new vibrant colors
                        funny_messages = [
                            "<#FF1493>🦶 My feet are getting stiff! Gotta move!",
                            "<#8A2BE2>⚡ Sudden energy burst incoming!",
                            "<#00BFFF>🏃‍♂️ Can't stay in one place, I'm restless!",
                            "<#FF4500>🔋 Feel like there's electricity in my legs!",
                            "<#00FF00>🐜 This place is full of ants! Moving away!",
                            "<#FF69B4>🎵 The music is making me move!",
                            "<#9932CC>😴 Standing still makes me sleepy, time to walk!",
                            "<#00CED1>🌪️ Tornado in my feet! Can't stop moving!",
                            "<#FF8C00>🔥 Hot floor! Hot floor! Gotta move!",
                            "<#87CEFA>🧊 Floor is too cold, need to warm up!",
                            "<#FFD700>🦋 Following invisible butterflies!",
                            "<#DA70D6>🎯 My GPS is acting crazy again!",
                            "<#40E0D0>🌊 Feeling the ocean waves in my soul!",
                            "<#F4A460>☕ Too much coffee! Can't sit still!",
                            "<#FF6347>🎪 The circus in my head says 'MOVE!'",
                            "<#00FA9A>🚀 Rocket fuel in my sneakers!",
                            "<#DDA0DD>🐸 Hop hop! Feeling froggy today!",
                            "<#7B68EE>✨ Sparkles are tickling my feet!",
                            "<#FFB6C1>🎲 Random dice rolled 'WALK'!",
                            "<#00FFFF>🤖 Beep boop! Movement protocol activated!",
                            "<#FFA07A>🍃 The wind is calling me to wander!",
                            "<#98FB98>🌟 Stars aligned for a perfect stroll!",
                            "<#F0E68C>🎈 Balloons in my stomach lifting me up!",
                            "<#20B2AA>⚡ Lightning bolt of energy struck!",
                            "<#FF1493>🎭 My inner dancer can't be contained!"
                        ]

                        random_message = random.choice(funny_messages)
                        await self.highrise.chat(random_message)

                # Wait for specified interval before moving again
                await asyncio.sleep(Config.RANDOM_MOVEMENT_INTERVAL)

            except asyncio.CancelledError:
                print("Random movement task cancelled.")
                break
            except Exception as e:
                print(f"Error in random movement loop: {e}")
                await asyncio.sleep(5) # Wait before retrying

    async def handle_outfit_add_command(self, user: User, message: str) -> None:
        """Handle /on command to add outfit item"""
        # Check if user has permission (admin/owner/VIP/moderator)
        is_allowed = (Config.is_admin(user.username) or 
                     Config.is_owner(user.username) or 
                     Config.is_vip(user.username) or 
                     user.username in self.detected_moderators)
        
        if not is_allowed:
            await self.highrise.chat(f"<#FF6B6B> ❌ @{user.username} Outfit commands are for VIP, moderators and admins only!")
            return

        try:
            result = await self.outfit_manager.add_outfit_item_command(user, message)
            await self.highrise.send_whisper(user.id, result)
            print(f"👔 /on command executed by {user.username}")
        except Exception as e:
            await self.highrise.chat(f"<#FF0000> ❌ Error in outfit command!")
            print(f"Error in /on command: {e}")

    async def handle_outfit_remove_command(self, user: User, message: str) -> None:
        """Handle /off command to remove outfit item"""
        # Check if user has permission (admin/owner/VIP/moderator)
        is_allowed = (Config.is_admin(user.username) or 
                     Config.is_owner(user.username) or 
                     Config.is_vip(user.username) or 
                     user.username in self.detected_moderators)
        
        if not is_allowed:
            await self.highrise.chat(f"<#FF6B6B> ❌ @{user.username} Outfit commands are for VIP, moderators and admins only!")
            return

        try:
            result = await self.outfit_manager.remove_outfit_item_by_number(user, message)
            await self.highrise.send_whisper(user.id, result)
            print(f"👔 /off command executed by {user.username}")
        except Exception as e:
            await self.highrise.chat(f"<#FF0000> ❌ Error in outfit command!")
            print(f"Error in /off command: {e}")

    async def handle_copy_outfit_command(self, user: User, message: str) -> None:
        """Handle /copy command to copy another user's outfit"""
        # Check if user has permission (admin/owner/VIP/moderator)
        is_allowed = (Config.is_admin(user.username) or 
                     Config.is_owner(user.username) or 
                     Config.is_vip(user.username) or 
                     user.username in self.detected_moderators)
        
        if not is_allowed:
            await self.highrise.chat(f"<#FF6B6B> ❌ @{user.username} Outfit commands are for VIP, moderators and admins only!")
            return

        try:
            result = await self.outfit_manager.copy_user_outfit_command(user, message)
            await self.highrise.send_whisper(user.id, result)
            print(f"👔 /copy command executed by {user.username}")
        except Exception as e:
            await self.highrise.chat(f"<#FF0000> ❌ Error in copy outfit command!")
            print(f"Error in /copy command: {e}")

    async def run(self, room_id, token) -> None:
        await __main__.main(self, room_id, token)


class FileWatcher(FileSystemEventHandler):
    def __init__(self, restart_callback):
        self.restart_callback = restart_callback
        self.last_restart = time.time()

    def on_modified(self, event):
        if event.is_directory:
            return

        # Only watch Python files
        if event.src_path.endswith('.py'):
            # Prevent rapid restarts
            current_time = time.time()
            if current_time - self.last_restart > 2:  # 2 seconds cooldown
                print(f"File {event.src_path} modified. Restarting bot...")
                self.last_restart = current_time
                self.restart_callback()

class WebServer():
    def __init__(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'your-secret-key-here'
        self.app.config['MAX_CONTENT_LENGTH'] = Config.MAX_FILE_SIZE

        # Create upload folder if it doesn't exist
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

        self.setup_routes()

    def setup_routes(self):
        @self.app.route('/')
        def index():
            # Get list of Python files in current directory
            files = [f for f in os.listdir('.') if f.endswith(('.py', '.json', '.txt', '.md'))]

            message = request.args.get('message')
            success = request.args.get('success') == 'true'

            return render_template('index.html', files=files, message=message, success=success)

        @self.app.route('/upload', methods=['POST'])
        def upload_file():
            if 'file' not in request.files:
                return redirect(url_for('index', message='No file selected', success='false'))

            file = request.files['file']
            if file.filename == '':
                return redirect(url_for('index', message='No file selected', success='false'))

            if file and self.allowed_file(file.filename):
                filename = secure_filename(file.filename)

                # Create backup if file exists
                if os.path.exists(filename):
                    backup_name = f"{filename}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy2(filename, backup_name)

                file.save(filename)
                return redirect(url_for('index', message=f'File {filename} uploaded successfully!', success='true'))

            return redirect(url_for('index', message='Invalid file type', success='false'))

        @self.app.route('/edit/<filename>')
        def edit_file(filename):
            if not self.safe_filename(filename):
                return redirect(url_for('index', message='Invalid filename', success='false'))

            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()

                message = request.args.get('message')
                success = request.args.get('success') == 'true'

                return render_template('edit.html', filename=filename, content=content, 
                                     message=message, success=success)
            except Exception as e:
                return redirect(url_for('index', message=f'Error reading file: {str(e)}', success='false'))

        @self.app.route('/edit/<filename>', methods=['POST'])
        def save_file(filename):
            if not self.safe_filename(filename):
                return redirect(url_for('index', message='Invalid filename', success='false'))

            content = request.form['content']

            try:
                # Create backup
                if os.path.exists(filename):
                    backup_name = f"{filename}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy2(filename, backup_name)

                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)

                return redirect(url_for('edit_file', filename=filename, 
                                      message='File saved successfully!', success='true'))
            except Exception as e:
                return redirect(url_for('edit_file', filename=filename, 
                                      message=f'Error saving file: {str(e)}', success='false'))

        @self.app.route('/download/<filename>')
        def download_file(filename):
            if not self.safe_filename(filename):
                return redirect(url_for('index', message='Invalid filename', success='false'))

            try:
                return send_file(filename, as_attachment=True)
            except Exception as e:
                return redirect(url_for('index', message=f'Error downloading file: {str(e)}', success='false'))

        @self.app.route('/delete/<filename>')
        def delete_file(filename):
            if not self.safe_filename(filename) or filename in ['main.py', 'config.py']:
                return redirect(url_for('index', message='Cannot delete core files', success='false'))

            try:
                # Create backup before deletion
                backup_name = f"deleted_{filename}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(filename, backup_name)
                os.remove(filename)

                return redirect(url_for('index', message=f'File {filename} deleted successfully!', success='true'))
            except Exception as e:
                return redirect(url_for('index', message=f'Error deleting file: {str(e)}', success='false'))

        @self.app.route('/restart')
        def restart_bot():
            # This will trigger the file watcher to restart the bot
            with open('main.py', 'a') as f:
                f.write('\n# Restart trigger\n')
            return redirect(url_for('index', message='Bot restart triggered!', success='true'))

        @self.app.route('/backup')
        def create_backup():
            try:
                backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.makedirs(backup_dir, exist_ok=True)

                # Backup important files
                important_files = ['main.py', 'config.py']
                for filename in important_files:
                    if os.path.exists(filename):
                        shutil.copy2(filename, os.path.join(backup_dir, filename))

                return redirect(url_for('index', message=f'Backup created: {backup_dir}', success='true'))
            except Exception as e:
                return redirect(url_for('index', message=f'Backup failed: {str(e)}', success='false'))

        @self.app.route('/config')
        def edit_config():
            return redirect(url_for('edit_file', filename='config.py'))

        @self.app.route('/logs')
        def view_logs():
            return jsonify({"message": "Logs feature coming soon!"})

        @self.app.route('/clear-logs')
        def clear_logs():
            return redirect(url_for('index', message='Logs cleared!', success='true'))

    def allowed_file(self, filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

    def safe_filename(self, filename):
        # Prevent directory traversal attacks
        return filename and not '..' in filename and not filename.startswith('/')

    def run(self) -> None:
        self.app.run(host=Config.WEB_HOST, port=Config.WEB_PORT, debug=False)

    def keep_alive(self):
        t = Thread(target=self.run)
        t.start()

class RunBot():
    room_id = Config.ROOM_ID
    bot_token = Config.BOT_TOKEN
    bot_file = Config.BOT_FILE
    bot_class = Config.BOT_CLASS

    def __init__(self) -> None:
        self.should_restart = False
        self.observer = None
        self.definitions = [
            BotDefinition(
                getattr(import_module(self.bot_file), self.bot_class)(),
                self.room_id, self.bot_token)
        ]
        self.setup_file_watcher()

    def setup_file_watcher(self):
        """Setup file watcher for auto-reload"""
        try:
            event_handler = FileWatcher(self.request_restart)
            self.observer = Observer()
            self.observer.schedule(event_handler, '.', recursive=False)
            self.observer.start()
            print("📁 File watcher started - Auto-reload enabled!")
        except Exception as e:
            print(f"Could not start file watcher: {e}")

    def request_restart(self):
        """Request a bot restart"""
        self.should_restart = True

    def run_loop(self) -> None:
        while True:
            try:
                self.should_restart = False
                print("🤖 Starting bot...")

                # Run the bot using asyncio.run for proper event loop management
                async def run_with_restart_check():
                    try:
                        # Create main task
                        main_task = asyncio.create_task(main(self.definitions))

                        # Check for restart every second
                        while not self.should_restart:
                            try:
                                await asyncio.wait_for(asyncio.shield(main_task), timeout=1.0)
                                break  # Bot finished normally
                            except asyncio.TimeoutError:
                                if main_task.done():
                                    break
                                continue
                            except Exception as e:
                                print(f"Bot error: {e}")
                                break

                        if self.should_restart:
                            print("🔄 Restarting bot due to file changes...")
                            main_task.cancel()
                            try:
                                await main_task
                            except asyncio.CancelledError:
                                pass

                            # Recreate bot instance
                            import importlib
                            importlib.reload(sys.modules[__name__])

                            self.definitions = [
                                BotDefinition(
                                    getattr(import_module(self.bot_file), self.bot_class)(),
                                    self.room_id, self.bot_token)
                            ]

                    except Exception as e:
                        print(f"Run error: {e}")

                # Run with proper event loop
                asyncio.run(run_with_restart_check())

            except Exception as e:
                import traceback
                print("An error occurred:")
                traceback.print_exc()
                time.sleep(2)
                continue

if __name__ == "__main__":
    WebServer().keep_alive()
    RunBot().run_loop()