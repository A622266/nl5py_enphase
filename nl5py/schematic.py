# Copyright 2024 Enphase Energy, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import pandas as pd
import numpy as np
from .nl5_dll.commands import *
import ctypes as ct

# decorator which will check for NL5 errors
def check(func):
    def checked(*args, **kwargs):
        returned = func(*args, **kwargs)

        # check for any NL5 errors and throw exception if there is an error
        error = NL5_GetError()
        if error != b"OK":
            raise Exception(error.decode("utf-8"))

        return returned

    return checked


class Schematic:
    @check
    def __init__(self, filename):
        self.circuit = NL5_Open(filename.encode())

    @check
    def set_value(self, name, value):
        NL5_SetValue(self.circuit, name.encode(), value)

    @check
    def set_text(self, name, text):
        NL5_SetText(self.circuit, name.encode(), text.encode())

    @check
    def get_value(self, name):
        value = ct.c_double()
        NL5_GetValue(self.circuit, name.encode(), value)
        return value.value

    @check
    def get_text(self, name, length=100):
        text = ct.create_string_buffer(length)
        NL5_GetText(self.circuit, name.encode(), text, length)
        return text.value.decode("utf-8")

    @check
    def simulate_transient(self, screen, step):
        NL5_SetStep(self.circuit, step)
        NL5_Start(self.circuit)
        NL5_Simulate(self.circuit, screen)

    @check
    def add_trace(self, name, trace_type="Func"):
        # map the correct trace adding function
        func = {
            "V": NL5_AddVTrace,
            "I": NL5_AddITrace,
            "P": NL5_AddPTrace,
            "Var": NL5_AddVarTrace,
            "Func": NL5_AddFuncTrace,
            "Data": NL5_AddDataTrace,
        }[trace_type]

        func(self.circuit, name.encode())

    @check
    def get_trace_number(self, trace):
        return NL5_GetTrace(self.circuit, trace.encode())

    @check
    def get_data_at(self, trace, n):
        trace_number = self.get_trace_number(trace)

        t = ct.c_double()
        data = ct.c_double()
        NL5_GetDataAt(self.circuit, trace_number, n, t, data)

        return t.value, data.value

    @check
    def get_trace_data(self, trace):
        trace_number = self.get_trace_number(trace)

        # get the data length
        n = NL5_GetDataSize(self.circuit, trace_number)

        # extract the data
        data = np.empty((2, n))
        for i in range(n):
            data[:, i] = self.get_data_at(trace, i)

        # convert to a pandas series
        return pd.Series(index=data[0, :], data=data[1, :], name=trace)

    def get_data(self, traces):
        return pd.concat(
            [self.get_trace_data(trace) for trace in traces], axis=1
        ).ffill()

    @check
    def set_ac_source(self, name):
        NL5_SetACSource(self.circuit, name.encode())

    @check
    def simulate_ac(self, start_frequency, stop_frequency, num_points, log_scale=True):
        NL5_SetAC(
            self.circuit, start_frequency, stop_frequency, num_points, int(log_scale)
        )
        NL5_CalcAC(self.circuit)

    @check
    def get_ac_trace_number(self, trace):
        return NL5_GetACTrace(self.circuit, trace.encode())

    @check
    def get_ac_data_at(self, trace, n):
        trace_number = self.get_ac_trace_number(trace)

        f = ct.c_double()
        mag = ct.c_double()
        phase = ct.c_double()
        NL5_GetACDataAt(self.circuit, trace_number, n, f, mag, phase)

        return f.value, mag.value, phase.value

    @check
    def get_ac_trace_data(self, trace):
        trace_number = self.get_ac_trace_number(trace)

        # get the data length
        n = NL5_GetACDataSize(self.circuit, trace_number)

        # extract the data
        data = np.empty((3, n))
        for i in range(n):
            data[:, i] = self.get_ac_data_at(trace, i)

        # convert to a dataframe with a hierarchical index
        df = pd.concat(
            {
                trace: pd.DataFrame(
                    index=data[0, :],
                    data={"magnitude": data[1, :], "phase": data[2, :]},
                )
            },
            axis=1,
        )

        return df

    @check
    def get_ac_data(self, traces):
        return pd.concat(
            [self.get_ac_trace_data(trace) for trace in traces], axis=1
        ).ffill()

    @check
    def save(self):
        NL5_Save(self.circuit)

    @check
    def saveas(self, filename):
        NL5_SaveAs(self.circuit, filename.encode())
