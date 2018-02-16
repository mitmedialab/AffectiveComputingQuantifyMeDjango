from logging import handlers
import os, stat
import pwd
import grp

class GroupWriteRotatingFileHandler(handlers.RotatingFileHandler):

    def doRollover(self):
        """
        Override base class method to make the new log file group writable.
        """
        # Rotate the file first.
        handlers.RotatingFileHandler.doRollover(self)

        log_stat = os.stat(self.baseFilename)

        # set the group of the log file to be the owner's main group
        # group_name = pwd.getpwuid(log_stat.st_uid).pw_name
        # os.chown(self.baseFilename, log_stat.st_uid, grp.getgrnam(group_name).gr_gid)

        # Add group write to the current permissions.
        currMode = log_stat.st_mode
        os.chmod(self.baseFilename, currMode | stat.S_IWGRP)

