import base64
from functools import partial
from os import stat
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import permissions
from django.http import Http404
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from radio.models import *
from radio.serializers import *
from rest_framework import generics
from rest_framework.parsers import JSONParser
from rest_framework.parsers import FileUploadParser
from rest_framework import status
import json
from uuid import UUID
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from radio.transmission import new_transmission_handler
from radio.utils import TransmissionDetails, getUserAllowedSystems, getUserAllowedTalkgroups
from radio.permission import Feeder, IsSAOrReadOnly, IsSAOrFeedUser, IsSAOrUser, IsSiteAdmin


class UserProfileList(APIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsSAOrUser]

    @swagger_auto_schema(tags=["UserProfile"])
    def get(self, request, format=None):
        user = request.user.userProfile
        if user.siteAdmin:
            userProfile = UserProfile.objects.all()
        else:
            userProfile = UserProfile.objects.filter(UUID=user.UUID)
        serializer = UserProfileSerializer(userProfile, many=True)
        return Response(serializer.data)


class UserProfileView(APIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsSAOrReadOnly]

    def get_object(self, UUID):
        try:
            return UserProfile.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["UserProfile"])
    def get(self, request, UUID, format=None):
        user = request.user.userProfile
        if user.siteAdmin or user.UUID == UUID:
            userProfile = self.get_object(UUID)
        else:
            return Response(status=401)
        serializer = UserProfileSerializer(userProfile)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["UserProfile"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "siteTheme": openapi.Schema(
                    type=openapi.TYPE_STRING, description="siteTheme"
                ),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="description"
                ),
                "siteAdmin": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description="Is user authorized to make changes",
                )                
            },
        ),
    )
    def put(self, request, UUID, format=None):
        user = request.user.userProfile
        if user.siteAdmin or user.UUID == UUID:
            userProfile = self.get_object(UUID)
        else:
            return Response(status=401)
        serializer = UserProfileSerializer(userProfile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["UserProfile"])
    def delete(self, request, UUID, format=None):
        user = request.user.userProfile
        if user.siteAdmin or user.UUID == UUID:
            userProfile = self.get_object(UUID)
        else:
            return Response(status=401)
        userProfile.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SystemACLList(APIView):
    queryset = SystemACL.objects.all()
    serializer_class = SystemACLSerializer
    permission_classes = [IsSiteAdmin]

    @swagger_auto_schema(tags=["SystemACL"])
    def get(self, request, format=None):
        SystemACLs = SystemACL.objects.all()
        serializer = SystemACLSerializer(SystemACLs, many=True)
        return Response(serializer.data)


class SystemACLCreate(APIView):
    queryset = SystemACL.objects.all()
    serializer_class = SystemACLSerializer
    permission_classes = [IsSiteAdmin]

    @swagger_auto_schema(
        tags=["SystemACL"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["name", "public"],
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="string"),
                "users": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="List of user UUID",
                ),
                "public": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Make viable to all users"
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)
        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()
        serializer = SystemACLSerializer(data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SystemACLView(APIView):
    queryset = SystemACL.objects.all()
    serializer_class = SystemACLSerializer
    permission_classes = [IsSiteAdmin]

    def get_object(self, UUID):
        try:
            return SystemACL.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["SystemACL"])
    def get(self, request, UUID, format=None):
        SystemACL = self.get_object(UUID)
        serializer = SystemACLSerializer(SystemACL)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["SystemACL"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="string"),
                "users": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="List of user UUID",
                ),
                "public": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Make viable to all users"
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        SystemACL = self.get_object(UUID)
        serializer = SystemACLSerializer(SystemACL, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["SystemACL"])
    def delete(self, request, UUID, format=None):
        SystemACL = self.get_object(UUID)
        SystemACL.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SystemList(APIView):
    queryset = System.objects.all()
    serializer_class = SystemSerializer
    permission_classes = [IsSAOrReadOnly]

    @swagger_auto_schema(tags=["System"])
    def get(self, request, format=None):
        user: UserProfile = request.user.userProfile
        if user.siteAdmin:
            Systems = System.objects.all()
        else:
            userACLs = []
            ACLs = SystemACL.objects.all()
            for ACL in ACLs:
                ACL: SystemACL
                if ACL.users.filter(UUID=user.UUID):
                    userACLs.append(ACL)
                elif ACL.public:
                    userACLs.append(ACL)
            Systems = System.objects.filter(systemACL__in=userACLs)
        serializer = SystemSerializer(Systems, many=True)
        return Response(serializer.data)


class SystemCreate(APIView):
    queryset = System.objects.all()
    serializer_class = SystemSerializer
    permission_classes = [IsSiteAdmin]

    @swagger_auto_schema(
        tags=["System"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["name", "systemACL"],
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="System Name"),
                "systemACL": openapi.Schema(
                    type=openapi.TYPE_STRING, description="System ACL UUID"
                ),
                "enableTalkGroupACLs": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Enable Talkgroup ACLs on system"),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        serializer = SystemSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SystemView(APIView):
    queryset = System.objects.all()
    serializer_class = SystemSerializer
    permission_classes = [IsSAOrReadOnly]

    def get_object(self, UUID):
        try:
            return System.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    def get_ACL(self, UUID):
        try:
            return SystemACL.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["System"])
    def get(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        userACLs = []
        ACLs = SystemACL.objects.all()
        for ACL in ACLs:
            ACL: SystemACL
            if ACL.users.filter(UUID=user.UUID):
                userACLs.append(ACL)
            elif ACL.public:
                userACLs.append(ACL)

        system: System = self.get_object(UUID)

        if user.siteAdmin:
            serializer = SystemSerializer(system)
            return Response(serializer.data)

        if system.systemACL.UUID in userACLs:
            serializer = SystemSerializer(system)
            return Response(serializer.data)
        else:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

    @swagger_auto_schema(
        tags=["System"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="string"),
                "systemACL": openapi.Schema(
                    type=openapi.TYPE_STRING, description="System ACL UUID"
                ),
                "enableTalkGroupACLs": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Enable Talkgroup ACLs on system"),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        data = JSONParser().parse(request)
        System = self.get_object(UUID)
        serializer = SystemSerializer(System, data=data, partial=True)
        if user.siteAdmin:
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
        else:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["System"])
    def delete(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        System = self.get_object(UUID)
        if user.siteAdmin:
            System.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(status=status.HTTP_401_UNAUTHORIZED)


class SystemForwarderList(APIView):
    queryset = SystemForwarder.objects.all()
    serializer_class = SystemForwarderSerializer
    permission_classes = [IsSiteAdmin]

    @swagger_auto_schema(tags=["SystemForwarder"])
    def get(self, request, format=None):
        SystemForwarders = SystemForwarder.objects.all()
        serializer = SystemForwarderSerializer(SystemForwarders, many=True)
        return Response(serializer.data)


class SystemForwarderCreate(APIView):
    queryset = SystemForwarder.objects.all()
    serializer_class = SystemForwarderSerializer
    permission_classes = [IsSiteAdmin]

    @swagger_auto_schema(
        tags=["SystemForwarder"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["name", "enabled"],
            properties={
                "name": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Forwarder Name"
                ),
                "enabled": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="enabled"
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        data["feedKey"] = uuid.uuid4()

        serializer = SystemSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SystemForwarderView(APIView):
    queryset = SystemForwarder.objects.all()
    serializer_class = SystemForwarderSerializer
    permission_classes = [IsSiteAdmin]

    def get_object(self, UUID):
        try:
            return SystemForwarder.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["SystemForwarder"])
    def get(self, request, UUID, format=None):
        SystemForwarder = self.get_object(UUID)
        serializer = SystemForwarderSerializer(SystemForwarder)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["SystemForwarder"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Forwarder Name"
                ),
                "enabled": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="enabled"
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        data = JSONParser().parse(request)
        SystemForwarder = self.get_object(UUID)
        if "feedKey" in data:
            del data["feedKey"]
        serializer = SystemForwarderSerializer(SystemForwarder, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["SystemForwarder"])
    def delete(self, request, UUID, format=None):
        SystemForwarder = self.get_object(UUID)
        SystemForwarder.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CityList(APIView):
    queryset = City.objects.all()
    serializer_class = CitySerializer
    permission_classes = [IsSAOrReadOnly]

    @swagger_auto_schema(tags=["City"])
    def get(self, request, format=None):
        Citys = City.objects.all()
        serializer = CitySerializer(Citys, many=True)
        return Response(serializer.data)


class CityCreate(APIView):
    queryset = City.objects.all()
    serializer_class = CitySerializer
    permission_classes = [IsSiteAdmin]

    @swagger_auto_schema(
        tags=["City"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["name"],
            properties={
                "name": openapi.Schema(
                    type=openapi.TYPE_STRING, description="City Name"
                ),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="description"
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        serializer = CitySerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CityView(APIView):
    queryset = City.objects.all()
    serializer_class = CitySerializer
    permission_classes = [IsSAOrReadOnly]

    def get_object(self, UUID):
        try:
            return City.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["City"])
    def get(self, request, UUID, format=None):
        City = self.get_object(UUID)
        serializer = CitySerializer(City)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["City"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(
                    type=openapi.TYPE_STRING, description="City Name"
                ),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="description"
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        if not user.siteAdmin:
            raise PermissionDenied
        data = JSONParser().parse(request)
        City = self.get_object(UUID)
        serializer = CitySerializer(City, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["City"])
    def delete(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        if not user.siteAdmin:
            raise PermissionDenied
        City = self.get_object(UUID)
        City.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AgencyList(APIView):
    queryset = Agency.objects.all()
    serializer_class = AgencyViewListSerializer
    permission_classes = [IsSAOrReadOnly]

    @swagger_auto_schema(tags=["Agency"])
    def get(self, request, format=None):
        Agencys = Agency.objects.all()
        serializer = AgencyViewListSerializer(Agencys, many=True)
        return Response(serializer.data)


class AgencyCreate(APIView):
    queryset = Agency.objects.all()
    serializer_class = AgencySerializer
    permission_classes = [IsSiteAdmin]

    @swagger_auto_schema(
        tags=["Agency"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["name", "city"],
            properties={
                "name": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Agency Name"
                ),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="description"
                ),
                "city": openapi.Schema(
                    type=openapi.TYPE_STRING, description="City UUID"
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        serializer = AgencySerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AgencyView(APIView):
    queryset = Agency.objects.all()
    serializer_class = AgencySerializer
    permission_classes = [IsSAOrReadOnly]

    def get_object(self, UUID):
        try:
            return Agency.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["Agency"])
    def get(self, request, UUID, format=None):
        Agency = self.get_object(UUID)
        serializer = AgencyViewListSerializer(Agency)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["Agency"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Agency Name"
                ),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="description"
                ),
                "city": openapi.Schema(
                    type=openapi.TYPE_STRING, description="City UUID"
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        if not user.siteAdmin:
            raise PermissionDenied
        data = JSONParser().parse(request)
        Agency = self.get_object(UUID)
        serializer = AgencySerializer(Agency, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["Agency"])
    def delete(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        if not user.siteAdmin:
            raise PermissionDenied
        Agency = self.get_object(UUID)
        Agency.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TalkGroupList(APIView):
    queryset = TalkGroup.objects.all()
    serializer_class = TalkGroupViewListSerializer
    permission_classes = [IsSAOrReadOnly]

    @swagger_auto_schema(tags=["TalkGroup"])
    def get(self, request, format=None):
        user: UserProfile = request.user.userProfile
        if user.siteAdmin:
            TalkGroups = TalkGroup.objects.all()
            serializer = TalkGroupViewListSerializer(TalkGroups, many=True)
        else:
            systemUUIDs, systems = getUserAllowedSystems(user.UUID)

            AllowedTalkgroups = []
            for system in systems:
                AllowedTalkgroups.extend(getUserAllowedTalkgroups(system, user.UUID))
                    
            serializer = TalkGroupViewListSerializer(AllowedTalkgroups, many=True)
        return Response(serializer.data)


class TalkGroupCreate(APIView):
    queryset = TalkGroup.objects.all()
    serializer_class = TalkGroupSerializer
    permission_classes = [IsSiteAdmin]

    @swagger_auto_schema(
        tags=["TalkGroup"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["system", "decimalID"],
            properties={
                "system": openapi.Schema(
                    type=openapi.TYPE_STRING, description="System UUID"
                ),
                "decimalID": openapi.Schema(
                    type=openapi.TYPE_STRING, description="decimalID"
                ),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="decimalID"
                ),
                "alphaTag": openapi.Schema(
                    type=openapi.TYPE_STRING, description="alphaTag"
                ),
                "encrypted": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="encrypted"
                ),
                "agency": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Agency UUIDs",
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        serializer = TalkGroupSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TalkGroupView(APIView):
    queryset = TalkGroup.objects.all()
    serializer_class = TalkGroupSerializer
    permission_classes = [IsSAOrReadOnly]

    def get_object(self, UUID):
        try:
            return TalkGroup.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["TalkGroup"])
    def get(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        talkGroup: TalkGroup = self.get_object(UUID)
        if user.siteAdmin:
            serializer = TalkGroupViewListSerializer(talkGroup)
            return Response(serializer.data)
        else:
            systemUUIDs, systems = getUserAllowedSystems(user.UUID)

            AllowedTalkgroups = []
            for system in systems:
                AllowedTalkgroups.extend(getUserAllowedTalkgroups(system, user.UUID))
                    
            if not talkGroup in AllowedTalkgroups:
                return Response(status=status.HTTP_401_UNAUTHORIZED)

        serializer = TalkGroupViewListSerializer(talkGroup)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["TalkGroup"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                #'system': openapi.Schema(type=openapi.TYPE_STRING, description='System UUID'),
                #'decimalID': openapi.Schema(type=openapi.TYPE_STRING, description='decimalID'),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="decimalID"
                ),
                "alphaTag": openapi.Schema(
                    type=openapi.TYPE_STRING, description="alphaTag"
                ),
                "encrypted": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="encrypted"
                ),
                "agency": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Agency UUIDs",
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        data = JSONParser().parse(request)
        TalkGroup = self.get_object(UUID)
        
        user: UserProfile = request.user.userProfile
        if not user.siteAdmin:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = TalkGroupSerializer(TalkGroup, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["TalkGroup"])
    def delete(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        if not user.siteAdmin:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        
        TalkGroup = self.get_object(UUID)
        TalkGroup.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class TalkGroupACLList(APIView):
    queryset = TalkGroupACL.objects.all()
    serializer_class = TalkGroupACLSerializer
    permission_classes = [IsSiteAdmin]

    @swagger_auto_schema(tags=["TalkGroupACL"])
    def get(self, request, format=None):
        TalkGroupACLs = TalkGroupACL.objects.all()
        serializer = TalkGroupACLSerializer(TalkGroupACLs, many=True)
        return Response(serializer.data)


class TalkGroupACLCreate(APIView):
    queryset = TalkGroupACL.objects.all()
    serializer_class = TalkGroupACLSerializer
    permission_classes = [IsSiteAdmin]

    @swagger_auto_schema(
        tags=["TalkGroupACL"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["name", "users", "defaultNewUsers", "defaultNewTalkgroups"],
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "users": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Talkgroup Allowed UUIDs",
                ),
                "defaultNewUsers": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Add New Users to ACL"
                ),
                "defaultNewTalkgroups": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Add New Talkgroups to ACL"
                ),
                "allowedTalkgroups": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Talkgroup Allowed UUIDs",
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        serializer = TalkGroupACLSerializer(data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TalkGroupACLView(APIView):
    queryset = TalkGroupACL.objects.all()
    serializer_class = TalkGroupACLSerializer
    permission_classes = [IsSiteAdmin] 

    def get_object(self, UUID):
        try:
            return TalkGroupACL.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["TalkGroupACL"])
    def get(self, request, UUID, format=None):
        TalkGroupACL = self.get_object(UUID)
        serializer = TalkGroupACLSerializer(TalkGroupACL)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["TalkGroupACL"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "users": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Talkgroup Allowed UUIDs",
                ),
                "defaultNewUsers": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Add New Users to ACL"
                ),
                "defaultNewTalkgroups": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Add New Talkgroups to ACL"
                ),
                "allowedTalkgroups": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Talkgroup Allowed UUIDs",
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        data = JSONParser().parse(request)
        TalkGroupACL = self.get_object(UUID)
        serializer = TalkGroupACLSerializer(TalkGroupACL, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["TalkGroupACL"])
    def delete(self, request, UUID, format=None):
        TalkGroupACL = self.get_object(UUID)
        TalkGroupACL.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



class SystemRecorderList(APIView):
    queryset = SystemRecorder.objects.all()
    serializer_class = SystemRecorderSerializer
    permission_classes = [IsSiteAdmin]

    @swagger_auto_schema(tags=["SystemRecorder"])
    def get(self, request, format=None):
        SystemRecorders = SystemRecorder.objects.all()
        serializer = SystemRecorderSerializer(SystemRecorders, many=True)
        return Response(serializer.data)


class SystemRecorderCreate(APIView):
    queryset = SystemRecorder.objects.all()
    serializer_class = SystemRecorderSerializer
    permission_classes = [IsSiteAdmin]

    @swagger_auto_schema(
        tags=["SystemRecorder"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["system", "siteID", "name", "user"],
            properties={
                "system": openapi.Schema(
                    type=openapi.TYPE_STRING, description="System UUID"
                ),
                "siteID": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Site ID"
                ),
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "enabled": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Enabled"
                ),
                "user": openapi.Schema(
                    type=openapi.TYPE_STRING, description="User UUID"
                ),  # Replace me with resuestuser
                "talkgroupsAllowed": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Talkgroups Allowed UUIDs",
                ),
                "talkgroupsDenyed": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Talkgroups Allowed UUIDs",
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        data["forwarderWebhookUUID"] = uuid.uuid4()

        serializer = SystemRecorderSerializer(data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SystemRecorderView(APIView):
    queryset = SystemRecorder.objects.all()
    serializer_class = SystemRecorderSerializer
    permission_classes = [IsSiteAdmin]

    def get_object(self, UUID):
        try:
            return SystemRecorder.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["SystemRecorder"])
    def get(self, request, UUID, format=None):
        SystemRecorder = self.get_object(UUID)
        serializer = SystemRecorderSerializer(SystemRecorder)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["SystemRecorder"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                #'system': openapi.Schema(type=openapi.TYPE_STRING, description='System UUID'),
                "siteID": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Site ID"
                ),
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "enabled": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Enabled"
                ),
                #'user': openapi.Schema(type=openapi.TYPE_STRING, description='User UUID'),
                "talkgroupsAllowed": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Talkgroups Allowed UUIDs",
                ),
                "talkgroupsDenyed": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Talkgroups Allowed UUIDs",
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        data = JSONParser().parse(request)
        SystemRecorder = self.get_object(UUID)
        serializer = SystemRecorderSerializer(SystemRecorder, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["SystemRecorder"])
    def delete(self, request, UUID, format=None):
        SystemRecorder = self.get_object(UUID)
        SystemRecorder.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UnitList(APIView):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [IsSAOrReadOnly]

    @swagger_auto_schema(tags=["Unit"])
    def get(self, request, format=None):
        user: UserProfile = request.user.userProfile
        if user.siteAdmin:
            Units = Unit.objects.all()
        else:
            systemUUIDs, systems = getUserAllowedSystems(user.UUID)
            Units = Unit.objects.filter(system__in=systemUUIDs)
            
        serializer = UnitSerializer(Units, many=True)
        return Response(serializer.data)


class UnitCreate(APIView):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [IsSiteAdmin]

    @swagger_auto_schema(
        tags=["Unit"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["system", "decimalID"],
            properties={
                "system": openapi.Schema(
                    type=openapi.TYPE_STRING, description="System UUID"
                ),
                "decimalID": openapi.Schema(
                    type=openapi.TYPE_STRING, description="System UUID"
                ),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Description"
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        serializer = UnitSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UnitView(APIView):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [IsSAOrReadOnly]

    def get_object(self, UUID):
        try:
            return Unit.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["Unit"])
    def get(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        unit:Unit = self.get_object(UUID)
        if user.siteAdmin:
            serializer = UnitSerializer(unit)
        else:
            systemUUIDs, systems = getUserAllowedSystems(user.UUID)
            if not unit.system in systems:
                return Response(status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = UnitSerializer(unit)
        return Response(serializer.data)
            

    @swagger_auto_schema(
        tags=["Unit"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Description"
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        if not user.siteAdmin:       
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = JSONParser().parse(request)
        Unit = self.get_object(UUID)
        serializer = UnitSerializer(Unit, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["Unit"])
    def delete(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        if not user.siteAdmin:       
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        Unit = self.get_object(UUID)
        Unit.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TransmissionUnitList(APIView):
    queryset = TransmissionUnit.objects.all()
    serializer_class = TransmissionUnitSerializer
    permission_classes = [IsSAOrReadOnly]

    @swagger_auto_schema(tags=["TransmissionUnit"])
    def get(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile

        TransmissionX:Transmission = Transmission.objects.get(UUID=UUID)
        Units = TransmissionX.units.all()

        if not user.siteAdmin:
            systemUUIDs, systems = getUserAllowedSystems(user.UUID)
            if TransmissionX.system in systems:
                SystemX:System = TransmissionX.system
                if SystemX.enableTalkGroupACLs:
                    talkgroupsAllowed = getUserAllowedTalkgroups(SystemX, user.UUID)
                    if not TransmissionX.talkgroup in talkgroupsAllowed:
                        return Response(status=status.HTTP_401_UNAUTHORIZED)
            else:
                return Response(status=status.HTTP_401_UNAUTHORIZED)

        
        serializer = TransmissionUnitSerializer(Units, many=True)       
        return Response(serializer.data)


# class TransmissionUnitCreate(APIView):
#     queryset = TransmissionUnit.objects.all()
#     serializer_class = TransmissionUnitSerializer

#     @swagger_auto_schema(tags=['TransmissionUnit'])
#     def post(self, request, format=None):
#         data = JSONParser().parse(request)

#         if not "UUID" in data:
#             data["UUID"] =  uuid.uuid4()

#         serializer = TransmissionUnitSerializer(data=data, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TransmissionUnitView(APIView):
    queryset = TransmissionUnit.objects.all()
    serializer_class = TransmissionUnitSerializer
    permission_classes = [IsSAOrReadOnly]


    def get_object(self, UUID):
        try:
            return TransmissionUnit.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["TransmissionUnit"])
    def get(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        TransmissionUnitX:TransmissionUnit = self.get_object(UUID)
        
        TransmissionX:Transmission = Transmission.objects.filter(units__in=TransmissionUnitX)

        if not user.siteAdmin:
            systemUUIDs, systems = getUserAllowedSystems(user.UUID)
            if TransmissionX.system in systems:
                SystemX:System = TransmissionX.system
                if SystemX.enableTalkGroupACLs:
                    talkgroupsAllowed = getUserAllowedTalkgroups(SystemX, user.UUID)
                    if not TransmissionX.talkgroup in talkgroupsAllowed:
                        return Response(status=status.HTTP_401_UNAUTHORIZED)
            else:
                return Response(status=status.HTTP_401_UNAUTHORIZED)

        serializer = TransmissionUnitSerializer(TransmissionX)
        return Response(serializer.data)

    # @swagger_auto_schema(tags=['TransmissionUnit'], request_body=openapi.Schema(
    #     type=openapi.TYPE_OBJECT,
    #     properties={
    #         'description': openapi.Schema(type=openapi.TYPE_STRING, description='Description'),
    #     }
    # ))
    # def put(self, request, UUID, format=None):
    #     data = JSONParser().parse(request)
    #     TransmissionUnit = self.get_object(UUID)
    #     serializer = TransmissionUnitSerializer(TransmissionUnit, data=data, partial=True)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response(serializer.data)
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # @swagger_auto_schema(tags=['TransmissionUnit'])
    # def delete(self, request, UUID, format=None):
    #     TransmissionUnit = self.get_object(UUID)
    #     TransmissionUnit.delete()
    #     return Response(status=status.HTTP_204_NO_CONTENT)


class TransmissionFreqList(APIView):
    queryset = TransmissionFreq.objects.all()
    serializer_class = TransmissionFreqSerializer
    permission_classes = [IsSAOrReadOnly]

    @swagger_auto_schema(tags=["TransmissionFreq"])
    def get(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile

        TransmissionX:Transmission = Transmission.objects.get(UUID=UUID)
        Freqs = TransmissionX.frequencys.all()

        if not user.siteAdmin:
            systemUUIDs, systems = getUserAllowedSystems(user.UUID)
            if TransmissionX.system in systems:
                SystemX:System = TransmissionX.system
                if SystemX.enableTalkGroupACLs:
                    talkgroupsAllowed = getUserAllowedTalkgroups(SystemX, user.UUID)
                    if not TransmissionX.talkgroup in talkgroupsAllowed:
                        return Response(status=status.HTTP_401_UNAUTHORIZED)
            else:
                return Response(status=status.HTTP_401_UNAUTHORIZED)

        
        serializer = TransmissionFreqSerializer(Freqs, many=True)       
        return Response(serializer.data)


class TransmissionFreqView(APIView):
    queryset = TransmissionFreq.objects.all()
    serializer_class = TransmissionFreqSerializer
    permission_classes = [IsSAOrReadOnly]


    def get_object(self, UUID):
        try:
            return TransmissionFreq.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["TransmissionFreq"])
    def get(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
        TransmissionFreqX:TransmissionFreq = self.get_object(UUID)
        
        TransmissionX:Transmission = Transmission.objects.filter(frequencys__in=TransmissionFreqX)

        if not user.siteAdmin:
            systemUUIDs, systems = getUserAllowedSystems(user.UUID)
            if TransmissionX.system in systems:
                SystemX:System = TransmissionX.system
                if SystemX.enableTalkGroupACLs:
                    talkgroupsAllowed = getUserAllowedTalkgroups(SystemX, user.UUID)
                    if not TransmissionX.talkgroup in talkgroupsAllowed:
                        return Response(status=status.HTTP_401_UNAUTHORIZED)
            else:                
                return Response(status=status.HTTP_401_UNAUTHORIZED)

        serializer = TransmissionFreqSerializer(TransmissionFreqX)
        return Response(serializer.data)


class TransmissionList(APIView):
    queryset = Transmission.objects.all()
    serializer_class = TransmissionSerializer
    permission_classes = [IsSAOrReadOnly]

    @swagger_auto_schema(tags=["Transmission"])
    def get(self, request, format=None):
        user: UserProfile = request.user.userProfile
      
        if user.siteAdmin:
            Transmissions = Transmission.objects.all()
        else:
            systemUUIDs, systems = getUserAllowedSystems(user.UUID)
            Transmissions = Transmission.objects.filter(system__in=systems)
            AllowedTransmissions = []
            for TransmissionX in Transmissions:
                SystemX:System = TransmissionX.system
                if SystemX.enableTalkGroupACLs:
                    talkgroupsAllowed = getUserAllowedTalkgroups(SystemX, user.UUID)
                    if  TransmissionX.talkgroup in talkgroupsAllowed:
                        AllowedTransmissions.append(TransmissionX)
                else:
                    AllowedTransmissions.append(TransmissionX)

        serializer = TransmissionSerializer(AllowedTransmissions, many=True)
        return Response(serializer.data)


class TransmissionCreate(APIView):
    queryset = Transmission.objects.all()
    serializer_class = TransmissionSerializer
    permission_classes = [Feeder]

    @swagger_auto_schema(
        tags=["Transmission"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["recorder", "json", "audio"],
            properties={
                #'system': openapi.Schema(type=openapi.TYPE_STRING, description='System UUID'),
                "recorder": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Recorder Key"
                ),
                "json": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Trunk-Recorder JSON"
                ),
                "audioFile": openapi.Schema(
                    type=openapi.TYPE_STRING, description="M4A Base64"
                ),
                "name": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Audio File Name"
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        try:
            Callback = new_transmission_handler(data)

            if not Callback:
                return Response(
                    "Not allowed to post this talkgroup",
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            Callback["UUID"] = uuid.uuid4()

            recorderX: SystemRecorder = SystemRecorder.objects.get(
                UUID=Callback["forwarderWebhookUUID"]
            )
            Callback["system"] = str(recorderX.system.UUID)

            TX = TransmissionSerializer(data=Callback, partial=True)

            if TX.is_valid():
                TX.save()
            return Response({"success": True})
        except Exception as e:
            return Response(str(e), status=status.HTTP_400_BAD_REQUEST)


class TransmissionView(APIView):
    queryset = Transmission.objects.all()
    serializer_class = TransmissionSerializer

    def get_object(self, UUID):
        try:
            return Transmission.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["Transmission"])
    def get(self, request, UUID, format=None):
        TransmissionX:Transmission = self.get_object(UUID)
        user: UserProfile = request.user.userProfile
      
        if not user.siteAdmin:
            systemUUIDs, systems = getUserAllowedSystems(user.UUID)
            if not TransmissionX.system in systems:
                return Response(status=status.HTTP_401_UNAUTHORIZED)
            SystemX:System = TransmissionX.system
            if SystemX.enableTalkGroupACLs:
                talkgroupsAllowed = getUserAllowedTalkgroups(SystemX, user.UUID)
                if not TransmissionX.talkgroup in talkgroupsAllowed:
                    return Response(status=status.HTTP_401_UNAUTHORIZED)
            

        serializer = TransmissionSerializer(TransmissionX)
        return Response(serializer.data)

    # @swagger_auto_schema(tags=['Transmission'], request_body=openapi.Schema(
    #     type=openapi.TYPE_OBJECT,
    #     properties={
    #         'description': openapi.Schema(type=openapi.TYPE_STRING, description='Description'),
    #     }
    # ))
    # def put(self, request, UUID, format=None):
    #     data = JSONParser().parse(request)
    #     Transmission = self.get_object(UUID)
    #     serializer = TransmissionSerializer(Transmission, data=data, partial=True)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response(serializer.data)
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["Transmission"])
    def delete(self, request, UUID, format=None):
        user: UserProfile = request.user.userProfile
      
        if not user.siteAdmin:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        Transmission = self.get_object(UUID)
        Transmission.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IncidentList(APIView):
    queryset = Incident.objects.all()
    serializer_class = IncidentSerializer

    @swagger_auto_schema(tags=["Incident"])
    def get(self, request, format=None):
        Incidents = Incident.objects.all()
        serializer = IncidentSerializer(Incidents, many=True)
        return Response(serializer.data)


class IncidentCreate(APIView):
    queryset = Incident.objects.all()
    serializer_class = IncidentCreateSerializer

    @swagger_auto_schema(
        tags=["Incident"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["system", "name", "transmission"],
            properties={
                "system": openapi.Schema(
                    type=openapi.TYPE_STRING, description="System UUID"
                ),
                "transmission": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="TRANMISSIONS UUID",
                ),
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Description"
                ),
                "agency": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Agency UUIDs",
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        serializer = IncidentCreateSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IncidentUpdate(APIView):
    queryset = Incident.objects.all()
    serializer_class = IncidentCreateSerializer

    def get_object(self, UUID):
        try:
            return Incident.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(
        tags=["Incident"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Description"
                ),
                "transmission": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="TRANMISSIONS UUID",
                ),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Description"
                ),
                "agency": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Agency UUIDs",
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        data = JSONParser().parse(request)
        Incident = self.get_object(UUID)
        serializer = IncidentCreateSerializer(Incident, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IncidentView(APIView):
    queryset = Incident.objects.all()
    serializer_class = IncidentSerializer

    def get_object(self, UUID):
        try:
            return Incident.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["Incident"])
    def get(self, request, UUID, format=None):
        Incident = self.get_object(UUID)
        serializer = IncidentSerializer(Incident)
        return Response(serializer.data)

    @swagger_auto_schema(tags=["Incident"])
    def delete(self, request, UUID, format=None):
        Incident = self.get_object(UUID)
        Incident.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ScanListList(APIView):
    queryset = ScanList.objects.all()
    serializer_class = ScanListSerializer

    @swagger_auto_schema(tags=["ScanList"])
    def get(self, request, format=None):
        ScanLists = ScanList.objects.all()
        serializer = ScanListSerializer(ScanLists, many=True)
        return Response(serializer.data)


class ScanListCreate(APIView):
    queryset = ScanList.objects.all()
    serializer_class = ScanListSerializer

    @swagger_auto_schema(
        tags=["ScanList"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["name", "public", "talkgroups"],
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Description"
                ),
                "public": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description="Wether it is shared or user-only",
                ),
                "talkgroups": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Talkgroup UUIDs",
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        # data["user"] = request.user.UserProfile.UUID

        serializer = ScanListSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ScanListView(APIView):
    queryset = ScanList.objects.all()
    serializer_class = ScanListSerializer

    def get_object(self, UUID):
        try:
            return ScanList.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["ScanList"])
    def get(self, request, UUID, format=None):
        ScanList = self.get_object(UUID)
        serializer = ScanListSerializer(ScanList)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["ScanList"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "owner": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Owner User UUID"
                ),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Description"
                ),
                "public": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Wether it is shared or user-only",
                ),
                "talkgroups": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Talkgroup UUIDs",
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        data = JSONParser().parse(request)
        ScanList = self.get_object(UUID)
        serializer = ScanListSerializer(ScanList, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["ScanList"])
    def delete(self, request, UUID, format=None):
        ScanList = self.get_object(UUID)
        ScanList.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ScannerList(APIView):
    queryset = Scanner.objects.all()
    serializer_class = ScannerSerializer

    @swagger_auto_schema(tags=["Scanner"])
    def get(self, request, format=None):
        scanner = Scanner.objects.all()
        serializer = ScannerSerializer(scanner, many=True)
        return Response(serializer.data)


class ScannerCreate(APIView):
    queryset = Scanner.objects.all()
    serializer_class = ScannerSerializer

    @swagger_auto_schema(
        tags=["Scanner"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["name", "public", "scanlists"],
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Description"
                ),
                "public": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description="Wether it is shared or user-only",
                ),
                "scanlists": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Scanlist UUIDs",
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        # data["user"] = request.user.UserProfile.UUID

        serializer = ScannerSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ScannerView(APIView):
    queryset = Scanner.objects.all()
    serializer_class = ScannerSerializer

    def get_object(self, UUID):
        try:
            return Scanner.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["Scanner"])
    def get(self, request, UUID, format=None):
        Scanner = self.get_object(UUID)
        serializer = ScannerSerializer(Scanner)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["Scanner"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "owner": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Owner User UUID"
                ),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Description"
                ),
                "public": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Wether it is shared or user-only",
                ),
                "scanlists": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Scanlist UUIDs",
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        data = JSONParser().parse(request)
        Scanner = self.get_object(UUID)
        serializer = ScannerSerializer(Scanner, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["Scanner"])
    def delete(self, request, UUID, format=None):
        Scanner = self.get_object(UUID)
        Scanner.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GlobalScanListList(APIView):
    queryset = GlobalScanList.objects.all()
    serializer_class = GlobalScanListSerializer

    @swagger_auto_schema(tags=["GlobalScanList"])
    def get(self, request, format=None):
        GlobalScanLists = GlobalScanList.objects.all()
        serializer = GlobalScanListSerializer(GlobalScanLists, many=True)
        return Response(serializer.data)


class GlobalScanListCreate(APIView):
    queryset = GlobalScanList.objects.all()
    serializer_class = GlobalScanListSerializer

    @swagger_auto_schema(
        tags=["GlobalScanList"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["name", "scanList", "enabled"],
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "scanList": openapi.Schema(
                    type=openapi.TYPE_STRING, description=" Scan List UUID"
                ),
                "enabled": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Enabled"
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        serializer = GlobalScanListSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GlobalScanListView(APIView):
    queryset = GlobalScanList.objects.all()
    serializer_class = GlobalScanListSerializer

    def get_object(self, UUID):
        try:
            return GlobalScanList.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["GlobalScanList"])
    def get(self, request, UUID, format=None):
        GlobalScanList = self.get_object(UUID)
        serializer = GlobalScanListSerializer(GlobalScanList)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["GlobalScanList"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "scanList": openapi.Schema(
                    type=openapi.TYPE_STRING, description=" Scan List UUID"
                ),
                "enabled": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Enabled"
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        data = JSONParser().parse(request)
        GlobalScanList = self.get_object(UUID)
        serializer = GlobalScanListSerializer(GlobalScanList, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["GlobalScanList"])
    def delete(self, request, UUID, format=None):
        GlobalScanList = self.get_object(UUID)
        GlobalScanList.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GlobalAnnouncementList(APIView):
    queryset = GlobalAnnouncement.objects.all()
    serializer_class = GlobalAnnouncementSerializer

    @swagger_auto_schema(tags=["GlobalAnnouncement"])
    def get(self, request, format=None):
        GlobalAnnouncements = GlobalAnnouncement.objects.all()
        serializer = GlobalAnnouncementSerializer(GlobalAnnouncements, many=True)
        return Response(serializer.data)


class GlobalAnnouncementCreate(APIView):
    queryset = GlobalAnnouncement.objects.all()
    serializer_class = GlobalAnnouncementSerializer

    @swagger_auto_schema(
        tags=["GlobalAnnouncement"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["name", "enabled"],
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Description"
                ),
                "enabled": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Enabled"
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        serializer = GlobalAnnouncementSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GlobalAnnouncementView(APIView):
    queryset = GlobalAnnouncement.objects.all()
    serializer_class = GlobalAnnouncementSerializer

    def get_object(self, UUID):
        try:
            return GlobalAnnouncement.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["GlobalAnnouncement"])
    def get(self, request, UUID, format=None):
        GlobalAnnouncement = self.get_object(UUID)
        serializer = GlobalAnnouncementSerializer(GlobalAnnouncement)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["GlobalAnnouncement"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Description"
                ),
                "enabled": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Enabled"
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        data = JSONParser().parse(request)
        GlobalAnnouncement = self.get_object(UUID)
        serializer = GlobalAnnouncementSerializer(
            GlobalAnnouncement, data=data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["GlobalAnnouncement"])
    def delete(self, request, UUID, format=None):
        GlobalAnnouncement = self.get_object(UUID)
        GlobalAnnouncement.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GlobalEmailTemplateList(APIView):
    queryset = GlobalEmailTemplate.objects.all()
    serializer_class = GlobalEmailTemplateSerializer

    @swagger_auto_schema(tags=["GlobalEmailTemplate"])
    def get(self, request, format=None):
        GlobalEmailTemplates = GlobalEmailTemplate.objects.all()
        serializer = GlobalEmailTemplateSerializer(GlobalEmailTemplates, many=True)
        return Response(serializer.data)


class GlobalEmailTemplateCreate(APIView):
    queryset = GlobalEmailTemplate.objects.all()
    serializer_class = GlobalEmailTemplateSerializer

    @swagger_auto_schema(
        tags=["GlobalEmailTemplate"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "type": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Email type"
                ),
                "HTML": openapi.Schema(type=openapi.TYPE_STRING, description="HTML"),
                "enabled": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Enabled"
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        serializer = GlobalEmailTemplateSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GlobalEmailTemplateView(APIView):
    queryset = GlobalEmailTemplate.objects.all()
    serializer_class = GlobalEmailTemplateSerializer

    def get_object(self, UUID):
        try:
            return GlobalEmailTemplate.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["GlobalEmailTemplate"])
    def get(self, request, UUID, format=None):
        GlobalEmailTemplate = self.get_object(UUID)
        serializer = GlobalEmailTemplateSerializer(GlobalEmailTemplate)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=["GlobalEmailTemplate"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name"),
                "type": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Email type"
                ),
                "HTML": openapi.Schema(type=openapi.TYPE_STRING, description="HTML"),
                "enabled": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Enabled"
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        data = JSONParser().parse(request)
        GlobalEmailTemplate = self.get_object(UUID)
        serializer = GlobalEmailTemplateSerializer(
            GlobalEmailTemplate, data=data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["GlobalEmailTemplate"])
    def delete(self, request, UUID, format=None):
        GlobalEmailTemplate = self.get_object(UUID)
        GlobalEmailTemplate.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SystemReciveRateList(APIView):
    queryset = SystemReciveRate.objects.all()
    serializer_class = SystemReciveRateSerializer

    @swagger_auto_schema(tags=["SystemReciveRate"])
    def get(self, request, format=None):
        SystemReciveRates = SystemReciveRate.objects.all()
        serializer = SystemReciveRateSerializer(SystemReciveRates, many=True)
        return Response(serializer.data)


class SystemReciveRateCreate(APIView):
    queryset = SystemReciveRate.objects.all()
    serializer_class = SystemReciveRateSerializer

    @swagger_auto_schema(
        tags=["SystemReciveRate"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["time", "rate"],
            properties={
                "time": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Email type"
                ),
                "rate": openapi.Schema(type=openapi.TYPE_STRING, description="HTML"),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        serializer = SystemReciveRateSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SystemReciveRateView(APIView):
    queryset = SystemReciveRate.objects.all()
    serializer_class = SystemReciveRateSerializer

    def get_object(self, UUID):
        try:
            return SystemReciveRate.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["SystemReciveRate"])
    def get(self, request, UUID, format=None):
        SystemReciveRate = self.get_object(UUID)
        serializer = SystemReciveRateSerializer(SystemReciveRate)
        return Response(serializer.data)

    # @swagger_auto_schema(tags=['SystemReciveRate'], request_body=openapi.Schema(
    #     type=openapi.TYPE_OBJECT,
    #     required=[],
    #     properties={
    #         'name': openapi.Schema(type=openapi.TYPE_STRING, description='Name'),
    #         'type': openapi.Schema(type=openapi.TYPE_STRING, description='Email type'),
    #         'description': openapi.Schema(type=openapi.TYPE_STRING, description='Description'),
    #         'enabled': openapi.Schema(type=openapi.TYPE_STRING, description='Enabled')
    #     }
    # ))
    # def put(self, request, UUID, format=None):
    #     data = JSONParser().parse(request)
    #     SystemReciveRate = self.get_object(UUID)
    #     serializer = SystemReciveRateSerializer(SystemReciveRate, data=data, partial=True)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response(serializer.data)
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["SystemReciveRate"])
    def delete(self, request, UUID, format=None):
        SystemReciveRate = self.get_object(UUID)
        SystemReciveRate.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CallList(APIView):
    queryset = Call.objects.all()
    serializer_class = CallSerializer

    @swagger_auto_schema(tags=["Call"])
    def get(self, request, format=None):
        Calls = Call.objects.all()
        serializer = CallSerializer(Calls, many=True, read_only=True)
        return Response(serializer.data)


class CallCreate(APIView):
    queryset = Call.objects.all()
    serializer_class = CallUpdateCreateSerializer

    @swagger_auto_schema(
        tags=["Call"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=[
                "trunkRecorderID",
                "startTime",
                "endTime",
                "units",
                "emergency",
                "encrypted",
                "frequency",
                "phase2",
                "talkgroup",
            ],
            properties={
                "trunkRecorderID": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Trunk Recorder ID"
                ),
                "startTime": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Start Time"
                ),
                "endTime": openapi.Schema(
                    type=openapi.TYPE_STRING, description="End Time"
                ),
                "units": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Unit Decimal IDs",
                ),
                "emergency": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Emergency Call"
                ),
                "active": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Active Call"
                ),
                "encrypted": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Encrypted Call"
                ),
                "frequency": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Frequency"
                ),
                "phase2": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Phase2"
                ),
                "talkgroup": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Talk Group DecimalID"
                ),
            },
        ),
    )
    def post(self, request, format=None):
        data = JSONParser().parse(request)

        if not "UUID" in data:
            data["UUID"] = uuid.uuid4()

        serializer = CallUpdateCreateSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CallUpdate(APIView):
    queryset = Call.objects.all()
    serializer_class = CallUpdateCreateSerializer

    def get_object(self, UUID):
        try:
            return Call.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(
        tags=["Call"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=[],
            properties={
                "endTime": openapi.Schema(
                    type=openapi.TYPE_STRING, description="End Time"
                ),
                "units": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Unit Decimal IDs or UUIDs",
                ),
                "active": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Active Call"
                ),
                "emergency": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Emergency Call"
                ),
                "encrypted": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Encrypted Call"
                ),
                "frequency": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Frequency"
                ),
                "phase2": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Phase2"
                ),
                "talkgroup": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Talk Group DecimalID or UUID"
                ),
            },
        ),
    )
    def put(self, request, UUID, format=None):
        data = JSONParser().parse(request)
        Call = self.get_object(UUID)
        serializer = CallUpdateCreateSerializer(Call, data=data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CallView(APIView):
    queryset = Call.objects.all()
    serializer_class = CallSerializer

    def get_object(self, UUID):
        try:
            return Call.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["Call"])
    def get(self, request, UUID, format=None):
        Call = self.get_object(UUID)
        serializer = CallSerializer(Call)
        return Response(serializer.data)

    @swagger_auto_schema(tags=["Call"])
    def delete(self, request, UUID, format=None):
        Call = self.get_object(UUID)
        Call.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SystemRecorderMetricsList(APIView):
    queryset = SystemRecorderMetrics.objects.all()
    serializer_class = SystemRecorderMetricsSerializer

    @swagger_auto_schema(tags=["SystemRecorderMetrics"])
    def get(self, request, format=None):
        SystemRecorderMetricss = SystemRecorderMetrics.objects.all()
        serializer = SystemRecorderMetricsSerializer(SystemRecorderMetricss, many=True)
        return Response(serializer.data)


# class SystemRecorderMetricsCreate(APIView):
#     queryset = SystemRecorderMetrics.objects.all()
#     serializer_class = SystemRecorderMetricsSerializer

#     @swagger_auto_schema(tags=['SystemRecorderMetrics'], request_body=openapi.Schema(
#         type=openapi.TYPE_OBJECT,
#         required=['time','rate'],
#         properties={
#             'time': openapi.Schema(type=openapi.TYPE_STRING, description='Email type'),
#             'rate': openapi.Schema(type=openapi.TYPE_STRING, description='HTML'),
#         }
#     ))
#     def post(self, request, format=None):
#         data = JSONParser().parse(request)

#         if not "UUID" in data:
#             data["UUID"] =  uuid.uuid4()

#         serializer = SystemRecorderMetricsSerializer(data=data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SystemRecorderMetricsView(APIView):
    queryset = SystemRecorderMetrics.objects.all()
    serializer_class = SystemRecorderMetricsSerializer

    def get_object(self, UUID):
        try:
            return SystemRecorderMetrics.objects.get(UUID=UUID)
        except UserProfile.DoesNotExist:
            raise Http404

    @swagger_auto_schema(tags=["SystemRecorderMetrics"])
    def get(self, request, UUID, format=None):
        SystemRecorderMetrics = self.get_object(UUID)
        serializer = SystemRecorderMetricsSerializer(SystemRecorderMetrics)
        return Response(serializer.data)

    # @swagger_auto_schema(tags=['SystemRecorderMetrics'], request_body=openapi.Schema(
    #     type=openapi.TYPE_OBJECT,
    #     required=[],
    #     properties={
    #         'name': openapi.Schema(type=openapi.TYPE_STRING, description='Name'),
    #         'type': openapi.Schema(type=openapi.TYPE_STRING, description='Email type'),
    #         'description': openapi.Schema(type=openapi.TYPE_STRING, description='Description'),
    #         'enabled': openapi.Schema(type=openapi.TYPE_STRING, description='Enabled')
    #     }
    # ))
    # def put(self, request, UUID, format=None):
    #     data = JSONParser().parse(request)
    #     SystemRecorderMetrics = self.get_object(UUID)
    #     serializer = SystemRecorderMetricsSerializer(SystemRecorderMetrics, data=data, partial=True)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response(serializer.data)
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=["SystemRecorderMetrics"])
    def delete(self, request, UUID, format=None):
        SystemRecorderMetrics = self.get_object(UUID)
        SystemRecorderMetrics.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
