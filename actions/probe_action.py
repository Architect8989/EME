from tools.shell import probe_system_identity


class ProbeAction:
    id = "probe.system_identity"

    def run(self):
        return probe_system_identity()
