import aiohttp, uuid, random, re
from urllib.parse import quote

class PASS_NICE:
    """
    NICE아이디 본인인증 요청을 자동화해주는 비공식적인 모듈입니다. [요청업체: 한국도로교통공사]

    V1.0.1

    - 기능
    - SMS 본인인증 기능을 지원합니다.
    - MVNO 포함 전체 통신사를 지원합니다.
    - aiohttp를 기반으로 비동기로 작동합니다.
    """

    def __init__(self, cellCorp: str):
        """
        파라미터:
            * cellCorp (str): 인증 요청 대상자의 통신사 | ['SK', 'KT', 'LG', 'SM', 'KM', 'LM'] (뒤의 M은 알뜰폰입니다.)
        """
        self.session = aiohttp.ClientSession()
        self.cellCorp, cellCorpList = cellCorp, ['SK', 'KT', 'LG', 'SM', 'KM', 'LM']
        self.is_initialized = False

        self.hostISPMapping = {"SK" or "SM": "COMMON_MOBILE_SKT", "KT" or "KM": "COMMON_MOBILE_KT", "LG" or "LM": "COMMON_MOBILE_LGU"}
        self.authType = "SMS" # to-do: add pass app verification

        if self.cellCorp not in cellCorpList:
            raise ValueError("올바른 통신사 값을 입력해주세요.")
    
    async def init_session(self) -> dict:
        """
        현재 클래스의 웹 세션을 초기화합니다.
        해당 과정 없이 인증을 진행할 수 없습니다.

        ```py
        await pass.init_session()
        # -> {"Success": Bool, "Message": "오류 메시지 (성공 시 공란)"}
        ```
        """

        if self.is_initialized:
            await self.session.close()
            return {"Success": False, "Message": "이미 초기화된 세션입니다."}

        async with self.session.get('https://www.ex.co.kr:8070/recruit/company/nice/checkplus_main_company.jsp') as response:
            response = await response.text()
        
        m = re.search(r'name=["\']m["\']\s+value=["\']([^"\']+)["\']', response).group(1)
        EncodeData = re.search(r'name=["\']EncodeData["\']\s+value=["\']([^"\']+)["\']', response).group(1)  
        
        wcCookie = f'{uuid.uuid4()}_T_{random.randint(10000, 99999)}_WC'  
        self.session.cookie_jar.update_cookies({'wcCookie': wcCookie})  

        await self.session.post('https://nice.checkplus.co.kr/CheckPlusSafeModel/checkplus.cb', data={'m': m, 'EncodeData': EncodeData})
        
        async with self.session.post('https://nice.checkplus.co.kr/cert/main/tracer') as response:
            IP = re.search(r'callTracerApiInput\(\s*"[^"]*",\s*"(\d{1,3}(?:\.\d{1,3}){3})",', await response.text()).group(1)

        if not IP:
            await self.session.close()
            return {"Success": False, "Message": "IP 정보 취득에 실패하였습니다."}

        await self.session.post('https://ifc.niceid.co.kr/TRACERAPI/inputQueue.do', data={
            "host": "COMMON_CHECKPLUS",
            "ip": IP,
            "loginId": wcCookie,
            "port": "80",
            "pageUrl": "service",
            "userAgent": ""
        })

        await self.session.post('https://ifc.niceid.co.kr/TRACERAPI/inputQueue.do', data={
            "host": "COMMON_MOBILE",
            "ip": IP,
            "loginId": wcCookie,
            "port": "80",
            "pageUrl": "mobile_cert",
            "userAgent": ""
        })

        await self.session.post('https://nice.checkplus.co.kr/cert/main/menu')
        
        await self.session.post('https://ifc.niceid.co.kr/TRACERAPI/inputQueue.do', data={
            "host": self.hostISPMapping.get(self.cellCorp),
            "ip": IP,
            "loginId": wcCookie,
            "port": "80",
            "pageUrl": "mobile_cert_telecom",
            "userAgent": ""
        })

        async with self.session.post('https://nice.checkplus.co.kr/cert/mobileCert/method', data={"selectMobileCo": self.cellCorp, "os": "Windows"}) as response:
            certInfoHash = re.search(r'<input\s+type=["\']hidden["\']\s+name=["\']certInfoHash["\']\s+value=["\']([^"\']+)["\']>', await response.text()).group(1)

        async with self.session.post('https://nice.checkplus.co.kr/cert/mobileCert/sms/certification',
            data = {
                "certInfoHash": certInfoHash,
                "mobileCertAgree": "Y"
            }
        ) as response:
            self.SERVICE_INFO = re.search(r'const\s+SERVICE_INFO\s*=\s*"([^"]+)"', await response.text()).group(1)
            self.captchaVersion = re.search(r'const\s+captchaVersion\s*=\s*"([^"]+)"', await response.text()).group(1)

        self.is_initialized = True

        return {'Success': True, "Message": ""}

    async def get_captcha(self) -> dict:
        """
        현재 클래스의 초기화된 세션을 기준으로, 인증 요청 전송시에 필요한 캡챠 이미지를 반환합니다.

        ```py
        await pass.get_captcha()
        # {"Success": Bool, "Message": "(오류)" || "Content": bytes (성공)}
        ``` 
        """
        if not self.is_initialized or not self.captchaVersion:
            await self.session.close()
            return {"Success": False, "Message": "세션이 초기화되지 않았습니다."}

        try:
            async with self.session.get(f'https://nice.checkplus.co.kr/cert/captcha/image/{self.captchaVersion}') as response:
                content = await response.content.read()
            
            return {"Success": True, "Content": content}
        
        except:
            return {"Success": False, "Message": "캡챠 이미지 확인 중 오류가 발생하였습니다."}

    async def send_SMS_verify(self, name: str, birthdate: str, phone: str, captchaAnswer: str) -> dict:
        """
        파라미터의 정보로 SMS 휴대폰 본인확인 요청을 전송합니다.

        파라미터:
            * name (str): 이름 (홍길동)
            * birthdate (str): 생년월일 (YYMMDDN) | N은 주민등록번호상 성별코드입니다.
            * phone (str): 휴대전화번호 (01012345678) | -(하이폰) 없이 작성해야 합니다.
            * captchaAnswer (str): 캡챠 코드 (XXXXXX) | 숫자만 작성해야 합니다.
        
        ```py
        await pass.send_SMS_verify("홍길동", "0102034", "01012345678", "123456")
        # {"Success": Bool, "Message": "오류 메시지 (성공 시 공란)"}
        ```
        """

        if not self.is_initialized or not self.captchaVersion:
            await self.session.close()
            return {"Success": False, "Message": "세션이 초기화되지 않았습니다."}
    
        async with self.session.post('https://nice.checkplus.co.kr/cert/mobileCert/sms/certification/proc', 
            headers={
                "X-Requested-With": "XMLHTTPRequest",
                "x-service-info": self.SERVICE_INFO
            }, data = {
                "userNameEncoding": quote(name),
                "userName": name,
                "myNum1": birthdate[0:6],
                "myNum2": birthdate[6],
                "mobileNo": phone,
                "captchaAnswer": captchaAnswer
            }
        ) as response:
            response = await response.json()
        
        if not response['code'] == "SUCCESS":
            await self.session.close()
            return {"Success": False, "Message": "올바른 인증 정보를 입력해주세요."}
        
        async with self.session.post('https://nice.checkplus.co.kr/cert/mobileCert/sms/confirm') as response:
            self.SERVICE_INFO = re.search(r'const\s+SERVICE_INFO\s*=\s*"([^"]+)"', await response.text()).group(1)

        self.name, self.birthdate, self.phone = name, birthdate, phone
        self.is_verify_sent = True

        return {"Success": True, "Message": ""}

    async def check_SMS_verify(self, sms_code: str):
        """
        전송된 SMS 코드를 확인합니다.

        파라미터:
            * sms_code (str): 휴대전화로 전송된 SMS 코드
        
        ```py
        await pass.check_SMS_verify("123456")
        # {"Success": Bool, "Message": "오류 메시지 (성공 시 공란)"}
        ```
        """

        if not self.is_verify_sent:
            await self.session.close()
            return {"Success": False, "Message": "SMS 코드를 전송하지 않았습니다."}

        async with self.session.post('https://nice.checkplus.co.kr/cert/mobileCert/sms/confirm/proc',
            headers={
                "X-Requested-With": "XMLHTTPRequest",
                "x-service-info": self.SERVICE_INFO
            },
            data={
                "certCode": sms_code
            }
        ) as response:
            response = await response.json()
        
        if response['code'] == "RETRY":
            await self.session.close()
            return {"Success": False, "Message": "올바른 인증코드를 입력해주세요."}

        if not response['code'] == "SUCCESS":
            await self.session.close()
            return {"Success": False, "Message": "알 수 없는 오류가 발생하였습니다."}

        await self.session.close()
        return {"Success": True, "Message": ""}