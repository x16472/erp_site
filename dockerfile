# 指定基礎映像檔（Base Image），此處使用微軟官方的 Windows Server Core 1809 版本
FROM mcr.microsoft.com/windows/servercore:1809
# 設定映像檔的元數據（Metadata）標籤，此處用來註明該映像檔的作者或維護者信箱
LABEL org.opencontainers.image.authors="dog0830430@gmail.com"
# 在這裡定義變數 NAME
ENV NAME="MyWebsite"
# 在映像檔建置過程中執行命令，此處調用 Windows 的 DISM 工具來啟用 IIS 網頁伺服器功能，且不自動重啟
RUN dism.exe /online /enable-feature /all /featurename:iis-webserver /NoRestart
# 切換並指定後續指令（如 COPY、CMD）在容器內執行的工作目錄
WORKDIR c:/inetpub/wwwroot
# 將目前主機目錄下的所有檔案與資料夾，複製到容器內的工作目錄（即 c:/inetpub/wwwroot）
COPY . .
# 設定容器啟動時預設執行的命令
CMD ["powershell"]