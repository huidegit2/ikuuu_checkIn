#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用邮件通知模块（纯 Python 标准库，无第三方依赖）。

GitHub Actions / 本地均可运行。读取以下环境变量：
  MAIL_AUTH  (必需) SMTP 授权码。QQ 邮箱需在「设置-账号-POP3/SMTP服务」生成，
             不是 QQ 登录密码。
  MAIL_TO    (必需) 收件邮箱，多个用逗号分隔。
  MAIL_USER  (可选) 发件邮箱，默认与 MAIL_TO 相同（自发自收）。
  MAIL_HOST  (可选) SMTP 主机，默认 smtp.qq.com。
  MAIL_PORT  (可选) 优先端口，默认依次尝试 465(SSL) 与 587(STARTTLS)。

设计原则：未配置授权码时静默跳过；任何发送异常都被吞掉并只打印日志，
绝不让「通知失败」把签到任务本身弄挂。
"""
import os
import ssl
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr, formatdate


def _env(name, default=""):
    return (os.environ.get(name) or "").strip() or default


def send_mail(subject, content, timeout=20):
    """发送纯文本通知邮件。返回 True/False。

    subject 建议形如「GLaDOS 签到通知」，content 为签到结果正文。
    """
    auth = _env("MAIL_AUTH")
    to_raw = _env("MAIL_TO")
    if not auth or not to_raw:
        print("[邮件] 未配置 MAIL_AUTH / MAIL_TO，跳过邮件通知")
        return False

    user = _env("MAIL_USER", to_raw.split(",")[0].strip())
    host = _env("MAIL_HOST", "smtp.qq.com")
    recipients = [x.strip() for x in to_raw.replace(";", ",").split(",") if x.strip()]
    try:
        preferred = int(_env("MAIL_PORT", "465"))
    except ValueError:
        preferred = 465
    ports = [preferred] + [p for p in (465, 587) if p != preferred]

    body = str(content or "")
    if len(body) > 20000:
        body = "...(前略)...\n" + body[-20000:]

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(str(subject or "签到通知"), "utf-8")
    msg["From"] = formataddr(("签到机器人", user))
    msg["To"] = ", ".join(recipients)
    msg["Date"] = formatdate(localtime=True)
    raw = msg.as_string()

    last_err = ""
    for port in ports:
        try:
            ctx = ssl.create_default_context()
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx)
            else:
                server = smtplib.SMTP(host, port, timeout=timeout)
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
            with server:
                server.login(user, auth)
                server.sendmail(user, recipients, raw)
            print("[邮件] 已发送至 {}（{}:{}）".format(", ".join(recipients), host, port))
            return True
        except Exception as e:  # noqa: BLE001
            last_err = "{}: {}".format(type(e).__name__, str(e)[:120])
            print("[邮件] {}:{} 发送失败 -> {}".format(host, port, last_err))
    print("[邮件] 所有端口尝试失败，放弃本次邮件通知")
    return False
