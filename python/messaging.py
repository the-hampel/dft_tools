import numpy
from inspect import getframeinfo, currentframe

# pytriqs
from pytriqs.archive import HDFArchive
from pytriqs.utility import mpi

# ****** Report Class ***************
class Report(object):
    """
        *Simple error handling.*
    """
    def __init__(self):
        self._verbosity=None
        self._filename=None


    def report_error(self, string):
        """
        Error

        :param string: stores the message with the description of the error
        :type string: str
        """
        comm = mpi.MPI.COMM_WORLD
        if mpi.is_master_node():
            if isinstance(string, str):

                inspect_data = getframeinfo(currentframe().f_back)
                self._print_message(input_message="Error: " + string +
                   "(file: %s, line: %s, in function: %s)" % (
                inspect_data.filename, inspect_data.lineno, inspect_data.function)+
                                                 " (in "+self.__class__.__name__+")")
            else:
                self._print_message("Wrong argument of the report_error" +
                        "function. Please send one string as an input parameter!")
            comm.Abort(-1)

    def make_verbose_statement(self,string):
        """
        Statement which can be switched off using verbosity parameter.

        :param string: stores the message with the description of the statement in the form of str
        :type string: str
        """
        if self._verbosity==2:
            if isinstance(string, str):
                self._print_message(input_message=string+
                                                 " (in "+self.__class__.__name__+")")
            else:
                self._print_message("Wrong argument of the warning" +
                       "function. Please send one string as an input parameter!")

    def make_statement(self, string):
        """
        Statement

        :param string: stores the message with the description of the statement in the form of str
        :type string: str
        """
        if isinstance(string, str):
            self._print_message(input_message=string+" (in "+self.__class__.__name__+")")
        else:
            self._print_message("Wrong argument of the warning" +
                   "function. Please send one string as an input parameter!")


    def report_warning(self, string):
        """
        Warning

        :param string: stores the message with the description of the warning in the form of str
        :type string: str
        """
        if self._verbosity==2:
            if isinstance(string, str):
                    self._print_message(input_message="Warning: "+
                                                                string+" (in "+self.__class__.__name__+")")
            else:
                self._print_message("Wrong argument of the warning" +
                       "function. Please send one string as an input parameter!")


    def _print_message(self,input_message=None):

       """

        :param input_message: Message for the user which will be formatted
        :type input_message: str

       """

       mpi.report(self._make_message(input_message=input_message))


    def _make_message(self,input_message=None):

        edge_line="!------------------------------------------------------------------------------------!"

        message="\n"+edge_line+"\n"
        message+=self._make_inner_message(input_message=input_message)
        message+=edge_line+"\n"

        return message


    def _make_inner_message(self,input_message=None):
        """
        Prepares message for the user. Removes "\n" from the given message
        and formats it so that it uniformly fills out a frame.
        Prints out nicely formatted message.

        :param input_message: Message for the user which will be formatted
        :type input_message: str

        """

        line="                                                                                     !"
        # -2 because we need space for '!' at the end and at the beginning, between is the comment broken into lines
        line_width=len(line)-2
        words=input_message.replace("\n"," ").split()

        current_line=""
        message=""
        for indx,word in enumerate(words):

            # in case word is really long, break it into lines so that each line fits into frame

            if len(word)>line_width:
                # we need to add symbol - to mark that we break a word so -1,
                # another -1 because we new space between frame and a broken word
                internal_width=line_width-2
                num_lines=int(len(word)/float(internal_width)+1.0) # take into account also potential unfilled last line

                for n in range(num_lines-1): # without the last line, a special case

                    message+=self._make_inner_message(input_message=word[n*internal_width:(n+1)*internal_width]+"-")

                # last line of a broken word
                n=+1
                message+=self._make_inner_message(input_message=word[n*internal_width:(n+1)*internal_width])

            # case of full lines
            elif (len(current_line)+len(" "+word))<line_width:
                current_line+=" "+word
            else:
                message+=line+ "\r!"+current_line+"\n"
                current_line=" "+word

            # last line which is not a full line
            if indx==(len(words)-1):
                message+=line+ "\r!"+current_line+"\n"

        return message


class Check(Report):

    n_inequiv_corr_shells=None

    def __init__(self):
        """
        *Checks if parameters have changed.*

        """

        super(Check, self).__init__()
        self._parameters_changed = False
        self._verbosity=None

        # These parameters have to be set to some valid value by inheriting class
        self._parameters_to_check = None
        self._old_parameters = None

        self._what_changed=[] #list with parameters which have changed
        self._critical_par_changed=False
        self._critical_par=None

        self.n_corr_shells=None
        self.n_k=None
        self._n_spin_blocs=None
        self.n_inequiv_corr_shells=None


    def reset_parameters_changed_attr(self):
        """
        Resets attribute necessary for *check_if_parameters_changed* to function properly.

        """
        self._parameters_changed = False


    def _check_if_parameter_changed(self, parameter_name=None, new_par=None, old_par=None):

        """
        Checks if parameter_name has changed in the dictionary with new parameters.

        :param parameter_name: name of parameter to check
        :type parameter_name: str

        :param new_par: item to check
        :type new_par: dict or list or primitive python type

        :param old_par: item from the previous run  to check
        :type old_par: dict or list or primitive python type
        """

        if isinstance(new_par, list):
            if isinstance(old_par, list):
                if len(new_par) == len(old_par):
                    for item in range(len(new_par)):
                        if isinstance(new_par[item],numpy.ndarray):
                            self._check_if_parameter_changed(parameter_name=parameter_name,
                                                         new_par=new_par[item],
                                                         old_par=old_par[item])
                        elif new_par[item] in old_par:
                            self._check_if_parameter_changed(parameter_name=parameter_name,
                                                         new_par=new_par[item],
                                                         old_par=old_par[item])
                        else:
                            self.report_par_change(item=parameter_name)
                            break

                else:

                    self.report_par_change(item=parameter_name)

            else:

                self.report_par_change(item=parameter_name)

        elif isinstance(new_par, dict):
            if isinstance(old_par, dict):
                if len(new_par) == len(old_par):
                    for item in new_par:
                        if isinstance(item,numpy.ndarray):
                            self._check_if_parameter_changed(parameter_name=parameter_name,
                                                             new_par=new_par[item],
                                                             old_par=old_par[item])

                        elif item in old_par:
                            self._check_if_parameter_changed(parameter_name=parameter_name,
                                                             new_par=new_par[item],
                                                             old_par=old_par[item])
                        else:
                            self.report_par_change(item=parameter_name)
                            break
                else:
                    self.report_par_change(item=parameter_name)

            else:

                self.report_par_change(item=parameter_name)

        elif isinstance(new_par, numpy.ndarray):
            if isinstance(old_par, numpy.ndarray):
                if not ( new_par.shape==old_par.shape and numpy.allclose(new_par, old_par)):

                    self.report_par_change(item=parameter_name)

            else:
                self.report_par_change(item=parameter_name)

        elif (new_par != old_par and not
        (new_par is None or old_par == "None")):

            self.report_par_change(item=parameter_name)


    @property
    def parameters_changed(self):

        return self._parameters_changed


    @parameters_changed.setter
    def parameters_changed(self,val):
        self.report_error("Attribute parameters_changed cannot be changed by user!")


    def check_parameters_changed(self, dictionary=None,hdf_dir=None):
        """
        Checks if parameters in sumk_dft have changed


        :param dictionary:  dictionary which stores key-value pairs which
                            will be compared with previous data  from hdf file
        :type dictionary: dict

        :param hdf_dir: name of the directory in hdf file where is the  dictionary to compare
        :type hdf_dir: str
        """

        if dictionary is None or not isinstance(dictionary,dict):
            self.report_error("Define dictionary with data to compare")

        # function check_if_parameters_changed from Check class which was inherited by Wannier2TRIQS
        self.reset_parameters_changed_attr()
        self._parameters_changed_core( items_to_check=dictionary.keys(),
                                          dictionary=dictionary,
                                          hdf_dir=hdf_dir)

        if self._parameters_changed:

            if self._critical_par_changed:
                for item in self._what_changed:
                    if item in self._critical_par:
                        self.make_statement("Critical parameter %s has changed since the "
                                            "last run. Please correct your input file!"%item)
                self.report_error("Invalid input data program aborted. Please correct input and rerun.")

            else:
                self._update_par_hdf(name=hdf_dir,
                                 dictionary=dictionary)


    def _update_par_hdf(self,name=None,dictionary=None):
        """
            Updates data in  hdf file.

            :param name: Name of the folder in hdf file where data will be updated, expects name from the main "directory"
            :type name: str

            :param dictionary:  dictionary with crucial data to update
            :type dictionary: dict

        """
        if mpi.is_master_node():
            try :
                ar = HDFArchive(self._filename + ".h5", "a")
                if not name in ar: ar.create_group(name)
                ar[name].update(dictionary)

                del ar
            except IOError:
                self.report_error("Appending to file "+self._filename + ".h5 failed!")


    def _parameters_changed_core(self, items_to_check=None,dictionary=None, hdf_dir=None):
        """

        Checks if parameters have changed -- core function.
        Private method of check class should be used
        together with check_parameters_changed
        Compares dictionary with old data and
        dictionary with new data

        :param items_to_check: list of items to check
        :type items_to_check: list of str

        :param dictionary: dictionary with values to check
        :type dictionary: dict

        :param hdf_dir: name of the directory in hdf file where is the  dictionary to compare,
                        it is expected to be in the main directory of hdf file
        :type hdf_dir: str

        :return: True if parameters have changed, False otherwise
        """
        self._parameters_to_check=dictionary
        if mpi.is_master_node():
            try:
                ar = HDFArchive(self._filename + ".h5", "a")
                if hdf_dir in ar:
                    old_parameters={}
                    for item in items_to_check:
                        if item in ar[hdf_dir]:
                            old_parameters[item] = ar[hdf_dir][item]
                        else:
                            self._parameters_changed = True
                            self.report_warning("Keyword %s not found in hdf file. New input "
                                                "parameter will be used in the calculation (update of software?)."%item)
                            del ar
                            return self._parameters_changed
                    self._old_parameters = old_parameters
                    for item in items_to_check:
                        if item in self._parameters_to_check:
                            if item in self._old_parameters:

                                self._check_if_parameter_changed(parameter_name=item,
                                                                 new_par=self._parameters_to_check[item],
                                                                 old_par=self._old_parameters[item])
                            else:
                                self.report_warning("Item %s not found in old parameters!" % item)
                        else:
                            self.report_warning("Item %s not found in the current parameters." % item)

                else:

                    self._parameters_changed = True

                del ar
            except IOError:

                self.report_error("Data from  file " + self._filename + ".h5 couldn't be read!")

        self._parameters_changed=mpi.bcast(self._parameters_changed)

        return self._parameters_changed


    def _convert_str_to_None(self, par=None):
        """
        Converts "None" to None.

        :param par: dictionary or item of dictionary
        :type par: dict
        """
        if isinstance(par, list):
            for item in range(len(par)):
                if par[item] == "None":
                    par[item] = None
                elif (isinstance(par[item], list) or
                              isinstance(par[item], dict)):
                    self._convert_str_to_None(par[item])

        elif isinstance(par, dict):
            for item in par:
                if par[item] == "None":
                    par[item] = None
                elif (    isinstance(par[item], list) or
                              isinstance(par[item], dict)):
                    self._convert_str_to_None(par[item])


    def _convert_None_to_str(self, par=None):
        """
        Converts None values to "None".

        :param par: dictionary or item of dictionary
        :type par: dict
        """
        if isinstance(par, list):
            for item in range(len(par)):
                if par[item] is None:
                    par[item] = "None"
                elif (    isinstance(par[item], list) or
                              isinstance(par[item], dict)):
                    self._convert_None_to_str(par[item])

        elif isinstance(par, dict):
            for item in par:
                if par[item] is None:
                    par[item] = "None"
                elif (    isinstance(par[item], list) or
                              isinstance(par[item], dict)):
                    self._convert_None_to_str(par[item])


    def report_par_change(self, item=None):
        """
        Makes a report  about the parameter which has changed.

        :param item: new dictionary with parameters to check
        :type: item: HDFArchive


        """

        if isinstance(item,str):
            self.report_warning("Previously parameter "+item+
                            " was set to %s. Now it is %s."
                            % (self._old_parameters[item], self._parameters_to_check[item]))
        else:
            self.report_warning("Previously parameter %s"
                            " was set to %s. Now it is %s."
                            % (item, self._old_parameters[item], self._parameters_to_check[item]))


        self._parameters_changed = True
        if item in self._critical_par: self._critical_par_changed=True
        self._what_changed.append(item)


    def check_n_corr(self,n_corr=None):
        """
        Checks whether number of correlated shell is valid.
        :param n_corr: number of correlated shell
        :type n_corr: int

        :return: bool, True if num_corr is valid otherwise False
        """
        return (isinstance(n_corr, int) and
              0 <= n_corr < self.n_corr_shells)


    def check_shell(self, x=None, t=None):
        """
        Checks if shell has a correct structure,

        :param x: shell to  check
        :type x: dictionary

        :param t: list of keywords which should be in the shell
        :type t: list

        :return: True if the structure of shell  is correct otherwise False
                 Structure of shell is considered to be correct if keywords of
                 x are equal to t and  for each key-value in x all values are of type int

        """

        return isinstance(x, dict) and  \
               isinstance(t, list) and \
               all([isinstance(key,str) for key in t ]) and \
               sorted(t)==sorted(x.keys()) \
               and all([isinstance(x[key],int) for key in x])\
               and x["dim"]<=(x["l"]*2+1)


    def check_n_k(self,n_k=None):
        return 0<n_k<self.n_k


    def check_n_spin_bloc(self,n_spin_bloc=None):
        return 0<=n_spin_bloc<self._n_spin_blocs


    def check_inequivalent_corr(self, n_corr=None):

        """
        Checks whether number of an inequivalent correlated shell is valid.

        :param n_corr: number of inequivalent correlated shell to be checked
        :type n_corr: int

        :return: bool, True if num_corr is valid otherwise it is False.
        """
        if not self.n_inequiv_corr_shells is None:

            return  (isinstance(n_corr, int) and
                     0 <= n_corr < self.n_inequiv_corr_shells)
        elif not self.__class__.n_inequiv_corr_shells is None:

            return  (isinstance(n_corr, int) and
                     0 <= n_corr < self.__class__.n_inequiv_corr_shells)
        else:
            self.report_error("Can't check if valid inequivalent shell!")


class Save(Report):
    """
    Groups methods responsible for saving dara to hdf file
    """

    def __init__(self):
        super(Save, self).__init__()
        self._filename = None
        self._parameters_changed = None


    def _save_par_hdf(self,name=None,dictionary=None):
        """
        Saves data to hdf file.

        :param name: Name of the folder in hdf file where data will be saved, expects name from the main "directory",
                    if name is not present it will be created
        :type name: str

        :param dictionary:  dictionary with crucial data to save, if
                            any entry is already present in hdf file it will be overwritten, mandatory parameter
        :type dictionary: dict

        """
        if mpi.is_master_node:

             try:

                ar = HDFArchive(self._filename + ".h5", "a")


                if not (name in ar):

                    self.report_warning("""Directory %s not found."""%name)
                    ar.create_group(name)



                for it in dictionary:
                    if it in ar[name]and not self._parameters_changed:
                        self.report_warning("Element "+it+" found in %s folder. Its previous content will be overwritten."%name)
                    ar[name][it] = dictionary[it]

                del ar

             except IOError:

                self.report_error("Appending "+ self._filename + ".h5 file failed!")


class Bracket(Report):
    """*Allows continuation over lines provided
    that the statement in interest is unclosed
    with brackets {, [, or (.*"""

    def __init__(self):
        super(Bracket, self).__init__()
        self.brackets = None
        self.brackets_patterns = {
            "]": "[",
            ")": "(",
            "}": "{",
            ">": "<"}


    def add_brackets(self, bracket_list=None):
        """Updates brackets record.

        :param bracket_list: list of brackets which will be added to the existing collection
        :type bracket_list: list of strings defined by self.brackets_patterns
        """

        if self.brackets is None:
            if not bracket_list == []:
                self.brackets = list(bracket_list)
        else:
            if not bracket_list == []:
                self.brackets.extend(bracket_list)


    def show_brackets(self):
        """Shows  currently stored brackets."""
        return self.brackets


    def find_parenthesis(self):
        """Looks for paired brackets"""
        if not self.brackets is None:
            ind_brackets_to_remove = []  # stores indexes with brackets to remove in ascending order but paired
            ind = 0
            brackets = list(self.brackets)
            for bracket in self.brackets:
                # closing bracket found
                if bracket in self.brackets_patterns:
                    ind_brackets_to_remove.extend([ind])
                    if self.brackets_patterns[bracket] in self.brackets:
                        counter = brackets.count(self.brackets_patterns[bracket])

                        current_position_old = self.brackets.index(
                            self.brackets_patterns[bracket])  # start from the first occurrence
                        current_position_new = current_position_old
                        for item in range(counter):

                            if self.brackets_patterns[bracket] in brackets[current_position_old:ind]:
                                current_position_new = brackets.index(self.brackets_patterns[bracket],
                                                                      current_position_old, ind)
                                current_position_old = current_position_new + 1  # look for the next possible occurrence

                            else:
                                break

                        brackets[current_position_new] = "Bracket_PAIR_BUSTED!"

                        ind_brackets_to_remove.extend([current_position_new])


                    else:

                        self.show_brackets()

                        self.report_error("Wrong parenthesis")
                ind += 1
            # remove closing brackets for which parenthesis was found
            brackets = []
            for bracket_ind in range(len(self.brackets)):
                if bracket_ind not in ind_brackets_to_remove:
                    brackets.extend([self.brackets[bracket_ind]])

            self.brackets = list(brackets)


    def reset_brackets(self):
        """Clears records of any brackets."""
        self.brackets = []


    def are_brackets_ended(self):
        """Checks if all  brackets were paired."""
        if not self.brackets:
            return True
        else:
            return False