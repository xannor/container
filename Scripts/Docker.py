import os
import sys
import subprocess
from datetime import datetime

IMAGES = []

REF = os.getenv("IMAGE_TAG")
EVENT = os.getenv("GITHUB_EVENT_NAME")
WORKSPACE = os.getenv("GITHUB_WORKSPACE")
SHA = os.getenv("GITHUB_SHA")
CHANGED_FILES = os.getenv("CHANGED_FILES").split(" ")


def append_docker_lables(dockerfile):
    with open(dockerfile, "a") as df:
        date = datetime.now()
        df.write("\n\nLABEL maintainer='hi@ludeeus.dev'\n")
        df.write(f"LABEL build.date='{date.year}-{date.month}-{date.day}'\n")
        df.write(f"LABEL build.sha='{SHA}'")


def main(runtype):
    if len(runtype) == 1:
        print("Runtype is missing")
        exit(1)

    # fmt: off
    # OS Base
    IMAGES.append(Image("alpine-base", "BaseImages/OS/Alpine.dockerfile", []))
    IMAGES.append(Image("debian-base", "BaseImages/OS/Debian.dockerfile", []))

    # Sorfware Base
    IMAGES.append(Image("go-base", "BaseImages/Go.dockerfile", ["alpine-base"]))
    IMAGES.append(Image("python-base", "BaseImages/Python.dockerfile", ["alpine-base"]))
    IMAGES.append(Image("dotnet-base", "BaseImages/Dotnet.dockerfile", ["debian-base"]))
    IMAGES.append(Image("nodejs-base", "BaseImages/Nodejs.dockerfile", ["alpine-base"]))

    # Reqular (amd64 only)
    IMAGES.append(Image("frontend", "Frontend.dockerfile", ["alpine-base", "nodejs-base"]))
    IMAGES.append(Image("netdaemon", "Netdaemon.dockerfile", ["dotnet-base", "debian-base"]))
    IMAGES.append(Image("integration", "Integration.dockerfile", ["alpine-base", "python-base"]))
    IMAGES.append(Image("monster", "Monster.dockerfile", ["alpine-base", "python-base", "integration"]))
    # fmt: on

    if "build" in runtype:
        build_all()
    if "publish" in runtype:
        publish_all()


class Image:
    def __init__(self, name, dockerfile, needs):
        self.name = name
        self.dockerfile = dockerfile
        self.needs = needs
        self.build = False
        self.published = False

    def constructCmd(self, publish=False):
        if not self.is_build_needed():
            print(f"Skipping build for {self.name}")
        buildx = "docker buildx build"
        if publish:
            append_docker_lables(f"./DockerFiles/{self.dockerfile}")
            args = " --output=type=image,push=true"
        elif "build" in sys.argv:
            args = " --load"
        else:
            args = " --output=type=image,push=false"
        if self.name.endswith("-base") and "build" not in sys.argv:
            args += " --platform linux/arm,linux/arm64,linux/amd64"
        else:
            args += " --platform linux/amd64"
        args += " --no-cache"
        args += " --compress"
        args += f" -t ludeeus/container:{self.name}"
        args += f" -f {WORKSPACE}/DockerFiles/{self.dockerfile}"
        args += " ."
        run_command(buildx + args)

    def build_image(self):
        self.constructCmd()
        self.build = True

    def publish_image(self):
        self.constructCmd(True)
        self.published = True

    def is_build_needed(self):
        if self.dockerfile in CHANGED:
            return True
        if self.needs:
            for name in self.needs:
                if get_dockerfile_from_name(name) in CHANGED:
                    return True
        if "rootfs" in CHANGED:
            return True
        return False

def get_next(sortkey):
    if "image" in sys.argv:
        image = sys.argv[-1]
        images = [x for x in IMAGES if x.name == image]
    else:
        images = IMAGES
    if sortkey == "build":
        return sorted(
            [x for x in images if not x.build], key=lambda x: x.needs, reverse=False
        )
    return sorted(
        [x for x in images if not x.published], key=lambda x: x.needs, reverse=False
    )

def get_dockerfile_from_name(name):
    return [x.dockerfile for x in images if x.name == name][0]

def run_command(command):
    print(command)
    cmd = subprocess.run([x for x in command.split(" ")])
    if cmd.returncode != 0:
        exit(1)


def build_all():
    while True:
        image = get_next("build")
        if not image:
            break
        image = image[0]
        if [x for x in IMAGES if x.name in image.needs and not x.build] and "image" not in sys.argv:
            print("Build strategy is not correct")
            exit(1)
        image.build_image()


def publish_all():
    while True:
        image = get_next("published")
        if not image:
            break
        image = image[0]
        image.publish_image()


print(os.environ)
main(sys.argv)
