FROM php:8.2-apache

# 安裝微軟 SQL Server 驅動所需的系統套件
RUN apt-get update && apt-get install -y \
    gnupg2 \
    apt-transport-https \
    && curl https://microsoft.com | gpg --dearmor > /etc/apt/trusted.gpg.d/microsoft.gpg \
    && curl https://microsoft.com > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 mssql-tools18 unixodbc-dev

# 安裝 PHP 擴充功能：pdo_mysql (連 MariaDB) 與 pdo_sqlsrv (連 MSSQL)
RUN docker-php-ext-install pdo_mysql \
    && pecl install pdo_sqlsrv sqsh \
    && docker-php-ext-enable pdo_sqlsrv
