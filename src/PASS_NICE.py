import httpx, re
from urllib.parse import quote

import random, uuid

from typing import Literal

class PASS_NICE:
    """
    NICE아이디 본인인증 요청을 자동화해주는 비공식적인 모듈입니다. [요청업체: 한국도로교통공사]

    V1.1.0

    - 기능
        - SMS 본인인증 기능을 지원합니다.
        - MVNO 포함 모든 통신사를 지원합니다.
        - `httpx`를 기반으로 100% 비동기로 작동합니다.
    
    - 기타
        - checkplusData 형식은 NICE아이디 사용하는 거의 모든 업체가 동일합니다.
        - 따라서, 다른 요청업체 엔드포인트만 따서 checkplusDataRequest URL을 바꾸시면 대부분 동작합니다.
    """

    def __init__(self, cellCorp: Literal["SK", "KT", "LG", "SM", "KM", "LM"]):
        """
        파라미터:
            * cellCorp (str): 인증 요청 대상자의 통신사
        """
        self.client = httpx.AsyncClient()
        
        self.cellCorp = cellCorp
        self.isInitialized = False

        self.__hostISPMapping = {
            "SK" or "SM": "COMMON_MOBILE_SKT",
            "KT" or "KM": "COMMON_MOBILE_KT",
            "LG" or "LM": "COMMON_MOBILE_LGU"
        }
        
        self.authType = "SMS" # to-do: add pass app verification
    
    async def initSession(self) -> dict:
        """
        현재 클래스의 세션을 초기화합니다.
        해당 과정 없이 인증을 진행할 수 없습니다.

        ```
        await pass.initSession()
        # -> {"Success": Bool, "Message": "오류 메시지 (성공 시 공란)"}
        ```
        """

        if self.isInitialized:
            return {"Success": False, "Message": "이미 초기화된 세션입니다."}

        try:
            checkplusDataRequest = await self.client.get('https://www.ex.co.kr:8070/recruit/company/nice/checkplus_main_company.jsp')
            checkplusData = checkplusDataRequest.text
            
            m = re.search(r'name=["\']m["\']\s+value=["\']([^"\']+)["\']', checkplusData).group(1)
            EncodeData = re.search(r'name=["\']EncodeData["\']\s+value=["\']([^"\']+)["\']', checkplusData).group(1)  

            wcCookie = f'{uuid.uuid4()}_T_{random.randint(10000, 99999)}_WC'  
            self.client.cookies.update({'wcCookie': wcCookie})  

        except:
            return {"Success": False, "Message": "checkplusData 요청 도중 문제가 발생하였습니다."}

        await self.client.post('https://nice.checkplus.co.kr/CheckPlusSafeModel/checkplus.cb',
            data = {'m': m, 'EncodeData': EncodeData}
        )
        
        try:
            mainTracerRequest = await self.client.post('https://nice.checkplus.co.kr/cert/main/tracer')
            IP = re.search(r'callTracerApiInput\(\s*"[^"]*",\s*"(\d{1,3}(?:\.\d{1,3}){3})",', mainTracerRequest.text).group(1)

        except:
            return {"Success": False, "Message": "tracer 요청 도중 문제가 발생하였습니다."}

        try:
            await self.client.post('https://nice.checkplus.co.kr/cert/main/menu')

            await self.client.post('https://ifc.niceid.co.kr/TRACERAPI/inputQueue.do',
                data = {
                    "host": self.__hostISPMapping.get(self.cellCorp),
                    "ip": IP,
                    "loginId": wcCookie,
                    "port": "80",
                    "pageUrl": "mobile_cert_telecom",
                    "userAgent": ""
                }
            )

        except:
            return {"Success": False, "Message": "tracerAPI 요청 도중 문제가 발생하였습니다."}
        

        try:
            methodRequest = await self.client.post(
                url = 'https://nice.checkplus.co.kr/cert/mobileCert/method', 
                data = {
                    "selectMobileCo": self.cellCorp, 
                    "os": "Windows"
                }
            )

            certInfoHash = re.search(r'<input\s+type=["\']hidden["\']\s+name=["\']certInfoHash["\']\s+value=["\']([^"\']+)["\']>', methodRequest.text).group(1)

        except:
            return {"Success": False, "Message": "method 요청 도중 문제가 발생하였습니다."}

        try:
            certProcRequest = await self.client.post(
                url = 'https://nice.checkplus.co.kr/cert/mobileCert/sms/certification',
                data = {
                    "certInfoHash": certInfoHash,
                    "mobileCertAgree": "Y"
                }
            )

            self.__SERVICE_INFO = re.search(r'const\s+SERVICE_INFO\s*=\s*"([^"]+)"', certProcRequest.text).group(1)
            self.__captchaVersion = re.search(r'const\s+captchaVersion\s*=\s*"([^"]+)"', certProcRequest.text).group(1)

        except:
            return {"Success": False, "Message": "certProc 요청 도중 문제가 발생하였습니다."}

        self.isInitialized = True

        return {'Success': True, "Message": ""}

    async def getCaptcha(self) -> dict:
        """
        현재 클래스의 초기화된 세션을 기준으로, 인증 요청 전송시에 필요한 캡챠 이미지를 반환합니다.

        ```
        await pass.getCaptcha()
        # {"Success": Bool, "Message": "(오류)" || "Content": bytes (성공)}
        ``` 
        """
        if not self.isInitialized or not self.__captchaVersion:
            return {"Success": False, "Message": "세션이 초기화되지 않았습니다."}

        try:
            captchaRequest = await self.client.get(f'https://nice.checkplus.co.kr/cert/captcha/image/{self.__captchaVersion}')
            content = captchaRequest.content
            
            return {"Success": True, "Content": content}
        
        except:
            return {"Success": False, "Message": "captcha 확인 요청 도중 문제가 발생하였습니다."}

    async def sendSMS(self, name: str, birthdate: str, phone: str, captchaAnswer: str) -> dict:
        """
        파라미터의 정보로 SMS 휴대폰 본인확인 요청을 전송합니다.

        파라미터:
            * name (str): 이름 (홍길동)
            * birthdate (str): 생년월일 (YYMMDDN) | N은 주민등록번호상 성별코드입니다.
            * phone (str): 휴대전화번호 (01012345678) | -(하이폰) 없이 작성해야 합니다.
            * captchaAnswer (str): 캡챠 코드 (XXXXXX) | 숫자만 작성해야 합니다.
        
        ```
        await pass.sendSMS("홍길동", "0102034", "01012345678", "123456")
        # {"Success": Bool, "Message": "오류 메시지 (성공 시 공란)"}
        ```
        """

        if not self.isInitialized or not self.__captchaVersion:
            return {"Success": False, "Message": "세션이 초기화되지 않았습니다."}
    
        try:
            smsProcRequest = await self.client.post(
                url = 'https://nice.checkplus.co.kr/cert/mobileCert/sms/certification/proc', 
                headers = {
                    "X-Requested-With": "XMLHTTPRequest",
                    "x-service-info": self.__SERVICE_INFO
                },
                data = {
                    "userNameEncoding": quote(name),
                    "userName": name,
                    "myNum1": birthdate[0:6], # 생년월일 6자리
                    "myNum2": birthdate[6], # 성별코드 1자리
                    "mobileNo": phone,
                    "captchaAnswer": captchaAnswer
                }
            )

        except:
            return {"Success": False, "Message": "smsProc 요청 도중 문제가 발생하였습니다."}
        
        if not smsProcRequest.json()['code'] == "SUCCESS":
            return {"Success": False, "Message": "올바른 본인인증 정보를 입력해주세요."}
        
        try:
            smsConfirmRequest = await self.client.post('https://nice.checkplus.co.kr/cert/mobileCert/sms/confirm')
            self.__SERVICE_INFO = re.search(r'const\s+SERVICE_INFO\s*=\s*"([^"]+)"', smsConfirmRequest.text).group(1)

        except:
            return {"Success": False, "Message": "smsConfirm 요청 도중 문제가 발생하였습니다."}

        self.name, self.birthdate, self.phone = name, birthdate, phone
        self.__isVerifySent = True

        return {"Success": True, "Message": ""}

    async def checkSMS(self, smsCode: str):
        """
        전송된 SMS 코드를 확인합니다.

        파라미터:
            * smsCode (str): 휴대전화로 전송된 SMS 코드
        
        ```py
        await pass.checkSMS("123456")
        # {"Success": Bool, "Message": "오류 메시지 (성공 시 공란)"}
        ```
        """

        if not self.isInitialized or not self.__captchaVersion:
            return {"Success": False, "Message": "세션이 초기화되지 않았습니다."}

        if not self.__isVerifySent:
            return {"Success": False, "Message": "아직 SMS 코드를 전송하지 않았습니다."}

        try:
            smsConfirmRequest = await self.client.post(
                url = 'https://nice.checkplus.co.kr/cert/mobileCert/sms/confirm/proc',
                headers = {
                    "X-Requested-With": "XMLHTTPRequest",
                    "x-service-info": self.__SERVICE_INFO
                },
                data = {
                    "certCode": smsCode
                }
            )
            
        except:
            return {"Success": False, "Message": "smsConfirm 요청 도중 문제가 발생하였습니다."}

        if smsConfirmRequest.json()['code'] == "RETRY":
            return {"Success": False, "Message": "올바른 인증코드를 입력해주세요."}

        if not smsConfirmRequest.json()['code'] == "SUCCESS":
            return {"Success": False, "Message": "smsConfirm 요청 도중 문제가 발생하였습니다."}

        return {"Success": True, "Message": ""}