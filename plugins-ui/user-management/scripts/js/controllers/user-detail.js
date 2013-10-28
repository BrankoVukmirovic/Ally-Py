define([
    'angular',
    'utils/sha512',
],
function(angular, sha) {
    'use strict';

    return function($scope, $q, User, UserDetailLoader, RoleListLoader) {
        
        $scope.initialize = function() {
            $scope.enabled = false;

            $scope.roleList = RoleListLoader();
            
            $scope.$watch('selectedUserId', function(selectedUserId) {
                if (selectedUserId === 0) {
                    $scope.newUser = {roles: {}};
                    for (var i in $scope.roleList) {
                        $scope.newUser.roles[$scope.roleList[i].Id] = false;
                    }
                    $scope.enabled = true;
                    $('#profile-button').tab('show');
                    $('#edit-profile-button').tab('show');
                } else if (selectedUserId !== null) {
                    $('#overview-button').tab('show');
                    $scope.loadUser(selectedUserId);
                }
            });
            $scope.$watch('user', function(user){
                if (user !== undefined) {
                    user.roles = {};
                    for (var i in $scope.roleList) {
                        user.roles[$scope.roleList[i].Id] = false;
                        var status = false;
                        for (var j in user.roleList) {
                            if (user.roleList[j].Id === $scope.roleList[i].Id) {
                                status = true;
                                break;
                            }
                        }
                        if (status === true) {
                            user.roles[$scope.roleList[i].Id] = true;
                        }
                    }
                    $scope.user = user;
                }
            });
            $scope.$watch('roleList', function(roleList){
                if (roleList !== undefined) {
                    $scope.roleList = roleList;
                }
            });
        };

        $scope.loadUser = function(userId) {
            $scope.user = UserDetailLoader(userId);
            $scope.enabled = true;
            $('#overview-button').tab('show');
        };

        $scope.unloadUser = function() {
            $scope.$parent.selectedUserId = null;
            $scope.user = undefined;
            $scope.enabled = false;
        };

        $scope.saveUser = function() {
            var user = {};
            var fields = ['Id', 'FirstName', 'LastName', 'Name', 'Password', 'EMail', 'PhoneNumber', 'Address'];
            for (var i = 0; i < fields.length; i = i + 1) {
                user[fields[i]] = $scope.user[fields[i]];
            }
            if (user.Password !== undefined) {
                user.Password = (new sha(user.Password, 'ASCII')).getHash('SHA-512', 'HEX');
            }
            
            if (user.Id === undefined) {
                var result = User.save(user);
                user.Id = result.Id;
            } else {
                User.update(user);
            }

            if (user.Password !== undefined) {
                User.update({Id: user.Id, Action: 'Password', NewPassword: user.Password});
            }

            if ($scope.user !== undefined) {
                for (var i in $scope.user.roles) {
                    if ($scope.user.roles[i] === true) {
                        User.update({Id: user.Id, Action: 'Role', Action2: i});
                    }
                }
            } else {
                for (var i in $scope.newUser.roles) {
                    if ($scope.newUser.roles[i] === true) {
                        User.update({Id: user.Id, Action: 'Role', Action2: i});
                    }
                }
            }

            $scope.$parent.loadUsers();
            $scope.unloadUser();
        }

        //
        $scope.initialize();

    };
});
