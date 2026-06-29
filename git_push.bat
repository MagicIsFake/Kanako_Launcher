@echo off
:: Tạo một dòng trống cho dễ nhìn
echo.

:: Yêu cầu nhập commit message và lưu vào biến 'commit_msg'
set /p commit_msg="Nhap commit message cua ban: "

:: Kiểm tra nếu bạn quen tay an Enter ma khong nhap gi, se tu dong lay message mac dinh
if "%commit_msg%"=="" set commit_msg="Update project"

git add .

:: Su dung bien 'commit_msg' da nhap o tren
git commit -m "%commit_msg%"

git branch -M main

git push -u origin main

pause