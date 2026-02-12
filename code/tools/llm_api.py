from json.decoder import JSONDecodeError
import re
import json
import logging
from openai import  OpenAI, Omit, omit
from openai.types.chat.completion_create_params import ResponseFormat
from tenacity import retry, wait_random_exponential, stop_after_attempt

from settings import LLMSettings as ST

class LLMCaller:
    account_num = 0
    cur_account_num = 0
    accounts = []
    gpt:OpenAI
    base_message = []
    temperature:float = 0.5
    
    def __init__(self, sysprompt = None) -> None:
        self.model = ST.MODEL
        self.accounts = ST.API_ACCOUNTS
        self.account_num = len(ST.API_ACCOUNTS)
        account = self.accounts[self.cur_account_num]
        self.temperature = ST.TEMPERATURE
        self.gpt = OpenAI(api_key=account["api_key"],base_url=account["base_url"])
        if sysprompt is not None:
            self.base_message.append({"role": "system", "content": sysprompt})
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"LLM API initialized, model name: {self.model}.")
        pass

    def change_account(self):
        if self.account_num == 1:
            # self.logger.error("Only one account info, can't change account.")
            return
        self.cur_account_num = (self.cur_account_num+1)%self.account_num
        account = self.accounts[self.cur_account_num]
        self.gpt = OpenAI(api_key=account["api_key"],base_url=account["base_url"])
        self.logger.info(f"Change api_key successfully.")
        return

    @retry(wait=wait_random_exponential(min=1, max=30), stop=stop_after_attempt(3))
    def _generation(self, prompt:str, rps_format:dict|Omit=omit) -> str:
        messages = self.base_message.copy()
        messages.append({"role": "user", "content": prompt})
        response = self.gpt.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format = rps_format,  # pyright: ignore[reportArgumentType]
            temperature=self.temperature,
            # add more parameters
        )
        if response.choices[0].message.content:
            return response.choices[0].message.content 
        else:
            self.change_account()
            raise ValueError("Empty response from API")
        
    def _filter_code(self, output:str) -> str:
        # extract java code from output
        java_pattern = r"```(?:[jJ]ava)?\n+([\s\S]*?)\n```"
        code = ""
        matches = re.findall(java_pattern, output, re.DOTALL)
        if len(matches) > 0: # if no code found, fix incomplete code
            code = matches[0]
        else: # select the longest one in matches
            incomplete_pattern = r"```(?:[jJ]ava)?\n+([\s\S]*?)$"
            icp_matches = re.findall(incomplete_pattern, output, re.DOTALL)
            if len(icp_matches) > 0:
                icp_code:str = icp_matches[0]
                # remove last @Test function
                last_test_pos = icp_code.rfind("@Test")
                code = icp_code[:last_test_pos] if last_test_pos != -1 else icp_code
                # check if code has unmatched braces
                open_braces = code.count('{')
                close_braces = code.count('}')
                if open_braces > close_braces:
                    code = code + "}" * (open_braces - close_braces)
        return code
    
    # get response surrounded by ```java````
    def get_response_code(self, prompt:str) -> list:
        try:
            response = self._generation(prompt)
            code = self._filter_code(response)
            return [code, response]
        except Exception as e:
            self.logger.error(f"Error occured while get code from llm api: {e}")
            return ["",""]

    # split json object from response
    def _handle_json_response(self, response):
        # self.logger.debug(f"Response: {response}")
        json_str = re.sub(r' //.*', '', response)
        json_pattern = r"```(?:[jJ]son)?\n+([\s\S]*?)\n```"
        matches = re.findall(json_pattern, json_str, re.DOTALL)
        if len(matches)>0:
            json_str = max(matches, key=len)
        obj = json.loads(json_str)
        self.logger.debug(f"Json object: {obj}")
        return obj
    
    # get response in json format
    def get_response_json(self, prompt:str):
        json_data = None
        response = ""
        try:
            response_format = { 'type': 'json_object' }
            response = self._generation(prompt, response_format)
            json_data = self._handle_json_response(response)
        except Exception as e:
            self.logger.error(f"{type(e)} occured while get json object from llm api: {e}")
            if isinstance(e, JSONDecodeError):
                response = f"{e}\n{response}"
        return [json_data, response]


# test
if __name__ == '__main__':
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    llm = LLMCaller()
    s = """
    """
    # match = llm.handle_json_response(s)
    # match = llm._filter_code(s)
    # print(match)