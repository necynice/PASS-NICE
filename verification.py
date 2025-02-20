import aiohttp, uuid, random, re
from urllib.parse import quote

class Verification():
    def __init__(self, cellCorp):
        self.session = aiohttp.ClientSession()
        self.cellCorp, cellCorpList = cellCorp, ['SK', 'KT', 'LG', 'SM', 'KM', 'LM']
        
        self.hostISPMapping = {"SK" or "SM": "COMMON_MOBILE_SKT", "KT" or "KM": "COMMON_MOBILE_KT", "LG" or "LM": "COMMON_MOBILE_LGU"}
        self.authType = "SMS" # to-do: add pass app verification

        if self.cellCorp not in cellCorpList:
            raise ValueError("올바른 통신사 값을 입력해주세요.")
        
    async def initSession(self):
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
            return {"Success": False, "Message": "서비스 정보 취득에 실패하였습니다."}

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

        async with self.session.post('https://nice.checkplus.co.kr/cert/mobileCert/sms/certification', data={"certInfoHash": certInfoHash, "mobileCertAgree": "Y"}) as response:
            self.SERVICE_INFO = re.search(r'const\s+SERVICE_INFO\s*=\s*"([^"]+)"', await response.text()).group(1)
            self.captchaVersion = re.search(r'const\s+captchaVersion\s*=\s*"([^"]+)"', await response.text()).group(1)

        return {'Success': True, "Message": "세션 초기화 성공"}

    async def getCaptcha(self):
        async with self.session.get(f'https://nice.checkplus.co.kr/cert/captcha/image/{self.captchaVersion}') as response:
            return await response.content.read()

    async def sendSmsCode(self, name: str, birthdate: str, phone: str, captchaAnswer: str):
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
        
        return {"Success": True, "Message": ""}

    async def checkSmsCode(self, smsCode: str):
        async with self.session.post('https://nice.checkplus.co.kr/cert/mobileCert/sms/confirm/proc',
            headers={
                "X-Requested-With": "XMLHTTPRequest",
                "x-service-info": self.SERVICE_INFO
            },
            data={
                "certCode": smsCode
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