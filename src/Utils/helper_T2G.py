# Copyright 2021-2023 FINCONS GROUP AG within the Horizon 2020
# European project SignON under grant agreement no. 101017255.

# Licensed under the Apache License, Version 2.0 (the "License"); 
# you may not use this file except in compliance with the License. 
# You may obtain a copy of the License at 

#     http://www.apache.org/licenses/LICENSE-2.0 

# Unless required by applicable law or agreed to in writing, software 
# distributed under the License is distributed on an "AS IS" BASIS, 
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
# See the License for the specific language governing permissions and 
# limitations under the License.

import requests

def map_language(input):
    switcher = {
        "VGT": "VGT",
        "SSP": "SSL",
        "BFI": "BSL",
        "ISG": "ISL",
        "DSE": "NGT",
        "BSL": "BSL"
    }
    return switcher.get(input)

def translate_text_to_gloss(to_translate, conf, language):
    lang = map_language(language).lower()
    url = 'http://text2gloss:' + conf['componentsPort']['t2g'] + '/text2gloss/'
    params = {
    'text': to_translate,
    'sign_lang': lang,
    'src_lang': 'English'
    }
    r = ""
    r = requests.get(url, params=params, timeout=(conf['externalServices']['timeout']))
    resp = r.json()['glosses']
    return resp