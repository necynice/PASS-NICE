import asyncio
from verification import Verification

async def main():
    name, birthdate, phone, ISP = "홍길동", "0701023", "01012345678", "KT"
    
    try:
        verification = Verification(ISP)

    except:
        return {"Success": False, "Message": "올바른 ISP 값을 입력해주세요."}
    
    initResult = await verification.initSession()
    if not initResult['Success']:
        return {"Success": False, "Message": initResult['Message']}

    captchaResult = await verification.getCaptcha()
    try:
        with open('captcha.png', 'wb') as f:
            f.write(captchaResult)
    
    except:
        return {"Success": False, "Message": "캡챠 이미지를 저장하던 중 오류가 발생하였습니다."}

    captchaCode = input("캡챠 코드를 입력해주세요: ")
    sendResult = await verification.sendSmsCode(name, birthdate, phone, captchaCode)
    if not sendResult['Success']:
        return {"Success": False, "Message": sendResult['Message']}
    
    smsCode = input("SMS로 전송된 코드를 입력해주세요: ")
    checkResult = await verification.checkSmsCode(smsCode)
    if not checkResult['Success']:
        return {"Success": False, "Message": checkResult['Message']}

    print("인증이 성공적으로 완료되었어요!")
    return {"Success": True, "Message": "인증이 성공적으로 완료되었습니다."}

asyncio.run(main())