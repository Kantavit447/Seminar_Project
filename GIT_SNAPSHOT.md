# การเก็บโปรเจกต์เก่าและ Clean ใน Git

`Project_meandyou/` เก็บไฟล์โปรเจกต์เก่า ณ วันที่ 26 กันยายน 2026 รวมการแก้ไขใน working tree ส่วน `Project_reasoning_clean/` เก็บ Clean Project และผล Golden engineering 10 ข้อที่ context 16384 พร้อมฉบับอ่านง่าย

ไม่รวม virtual environment, ไฟล์ตั้งค่าลับ และสำเนาสำรองในเครื่อง ผลการทดลองอื่นที่อยู่ใต้กฎ ignore เดิมไม่ได้ถูกเพิ่มโดยอัตโนมัติ

## ไลบรารีภายนอกของโปรเจกต์เก่า

`Project_meandyou/llama_index/` เป็น submodule จาก run-llama/llama_index ที่ commit `c80992f18461f86695162a1a5f8333ac5b6d6453` การแก้ไขในเครื่องจำนวน 4 ไฟล์เก็บไว้ใน `vendor_patches/llama_index.patch`

หลัง clone repository ใหม่ ให้รันจากโฟลเดอร์หลักเพื่อเรียกคืนไลบรารีและการแก้ไข:

```powershell
git submodule update --init --recursive
git -C Project_meandyou/llama_index apply --check ../../vendor_patches/llama_index.patch
git -C Project_meandyou/llama_index apply ../../vendor_patches/llama_index.patch
```

เครื่องเดิมมีการแก้ไขเหล่านี้อยู่แล้ว ไม่ต้อง apply patch ซ้ำ และ Git อาจแสดง submodule ว่ามีการแก้ไข ซึ่งเป็นสถานะที่คาดไว้

## สำรอง Git history เดิมในเครื่อง

Git history เดิมของ Project_meandyou ถูกเก็บที่ `C:\NitiBench\.git\local-repo-backups\Project_meandyou-20260926.git` และสำรอง index ของ repository หลักก่อนจัดโครงสร้างไว้ข้างกัน ข้อมูลสำรองภายใต้ `.git` ไม่ถูก push ขึ้น GitHub โค้ดต้นทางไม่ได้ถูกแก้เพื่อจัดโครงสร้างนี้
