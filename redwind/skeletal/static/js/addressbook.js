(function(){
    $(document).ready(function() {
        $('#fetch').click(function(){
            $.get('/api/fetch_profile',
                  {'url': $('#url').val()},
                  function(data, status){

                      var name = data['name'];
                      var photo = data['photo'];
                      var twitter = data['twitter'];
                      var facebook = data['facebook'];

                      if (name) {
                          $("#person").val(name);
                      }
                      if (photo) {
                          $("#photo").val(photo);
                      }
                      if (twitter) {
                          $("#twitter").val(twitter);
                      }
                      if (facebook) {
                          $("#facebook").val(facebook);
                      }

                  });
        });


    });
})();
